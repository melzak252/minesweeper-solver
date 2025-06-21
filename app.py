import asyncio
from enum import Enum
from pathlib import Path
from random import choice, sample, choices
from typing import List

import parsel
from playwright.async_api import async_playwright, Page, Locator, ElementHandle

from solver import LostException, MinesweeperSolver, WinException


class GameLevel(Enum):
    BEGINNER = 1
    EASY = 2
    ADVANCED = 3
    EXPERT = 4

    def __str__(self):
        return self.name.lower()

    @staticmethod
    def from_string(s: str):
        try:
            return GameLevel[s.upper()]
        except KeyError:
            raise ValueError()


GAME_LEVEL_SIZE = {
    GameLevel.BEGINNER: (8, 8),
    GameLevel.EASY: (12, 12),
    GameLevel.ADVANCED: (16, 16),
    GameLevel.EXPERT: (16, 30),
}

GAME_LEVEL_MINES = {
    GameLevel.BEGINNER: 10,
    GameLevel.EASY: 22,
    GameLevel.ADVANCED: 40,
    GameLevel.EXPERT: 99,
}


class MineSweeperPlayer:
    URL = "https://saper-online.pl/gra.php"

    def __init__(
        self,
        game_level=GameLevel.BEGINNER,
        nick="Melzak",
        wins=5,
        headless=False,
        loss_treshold=10,
    ):
        self.game_level = game_level
        self.nick = nick
        self.wins = wins
        self.headless = headless
        self.loss_treshold = 10
        self.page: Page = None
        self.solver: MinesweeperSolver = None

    async def setup_game(self, page: Page):
        self.page = page
        await page.goto(self.URL)

        try:
            el = await page.wait_for_selector(".fc-button", timeout=5000)
            await el.click()
        except Exception as e:
            print(f"Nie udało się zaakceptować ciasteczek: {e}")

        try:
            await page.wait_for_selector("#cookieBox", timeout=5000)
            await page.locator(".button.blue", has_text="Rozumiem, akceptuję!").click(
                timeout=2000
            )
        except Exception as e:
            print(f"Nie udało się zaakceptować ciasteczek: {e}")

        try:
            await page.locator(".button.green", has_text="Zmień nazwę").click()
            login_input = await page.wait_for_selector("#login")
            await login_input.fill("")
            await login_input.fill(self.nick)
            await page.locator(".button.blue", has_text="Zmień").click()
        except Exception as e:
            print(f"Nie udało się zmienić nazwy: {e}")

        await page.select_option("#poziomValue", str(self.game_level.value))
        await page.keyboard.press("F2")

        await asyncio.sleep(1)  # czekaj aż plansza się załaduje

        board = await self.to_board(page)
        self.solver = MinesweeperSolver(
            board,
            GAME_LEVEL_SIZE[self.game_level],
            self.page,
            GAME_LEVEL_MINES[self.game_level],
        )

    async def to_board(self, page: Page) -> List[List[Locator]]:
        game = page.locator("#Gra")
        board = []
        rows, cols = GAME_LEVEL_SIZE[self.game_level]

        for row in range(rows):
            row_elements = []
            for col in range(cols):
                cell = game.locator(f'[id="{row}-{col}"]')
                row_elements.append(cell)
            board.append(row_elements)

        return board

    async def get_time_info(self):
        czas = await self.page.query_selector("#CzasInfo")
        return await czas.inner_text()

    async def new_game(self):
        await self.page.keyboard.press("F2")
        board = await self.to_board(self.page)
        self.solver = MinesweeperSolver(
            board,
            GAME_LEVEL_SIZE[self.game_level],
            self.page,
            GAME_LEVEL_MINES[self.game_level],
        )

    async def random_moves(self, n: int = 5):
        moves = self.solver.get_unmarked()
        if len(moves) < n:
            r, c = choices(moves)[0]
            await self.solver.click(r, c, self.page)
        else:
            for r, c in sample(moves, n):
                await self.solver.click(r, c, self.page)

    async def solve(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            await self.setup_game(page)
            loses = 0

            while self.wins > 0:
                try:
                    r, c = GAME_LEVEL_SIZE[self.game_level]
                    await self.solver.click(r // 2 - 1, c // 2 - 1, page)
                    await self.random_moves(3)
                    while True:
                        await self.solver.update_board(page)
                        moves = self.solver.find_safe_moves()
                        if moves:
                            for r, c in moves:
                                await self.solver.click(r, c, page)
                            continue

                        moves = self.solver.probability()
                        if not moves:
                            time_info = await self.get_time_info()
                            raise WinException(f"Wygrana w {time_info}s")

                        r, c = choice(moves)
                        await self.solver.click(r, c, page)

                except WinException as win:
                    print(win)
                    czas = float(await self.get_time_info())
                    self.wins -= 1
                    await self.new_game()

                except LostException:
                    czas = await self.get_time_info()
                    print(f"Przegrana w {czas}")
                    if float(czas) > 2.0:
                        Path("loses").mkdir(exist_ok=True)
                        self.solver.save_state(f"loses/lose_{loses}.txt")
                        loses += 1
                    await self.new_game()

                except Exception as e:
                    print(f"Błąd: {e}")
                    break

            await browser.close()


def argparse_args():
    import argparse

    parser = argparse.ArgumentParser(description="MineSweeper Player")
    parser.add_argument(
        "--level",
        type=GameLevel.from_string,
        default=GameLevel.BEGINNER,
        choices=list(GameLevel),
        help="Game level to play",
    )
    parser.add_argument("--nick", type=str, default="Melzak", help="Player nickname")
    parser.add_argument(
        "--wins", type=int, default=10, help="Number of wins to achieve"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the browser in headless mode (default is False)",
    )

    return parser.parse_args()


async def main():
    args = argparse_args()
    player = MineSweeperPlayer(
        game_level=args.level, nick=args.nick, wins=args.wins, headless=args.headless
    )
    await player.solve()


if __name__ == "__main__":
    asyncio.run(main())
