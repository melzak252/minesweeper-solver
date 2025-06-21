import asyncio
from itertools import batched
from typing import List, Tuple
from random import choice

import parsel
from playwright.async_api import async_playwright, Page, Locator, ElementHandle


class LostException(Exception):
    pass


class WinException(Exception):
    pass


class MinesweeperSolver:
    def __init__(
        self, board: List[List], board_size: Tuple[int, int], page, mines: int
    ):
        self.page = page
        self.raw_board: List[List[ElementHandle]] = board  # Playwright Locators
        self.board: List[List[int | None]] = []
        self.mines = mines
        self.mines_found = 0
        self.board_rows, self.board_cols = board_size
        tiles = self.board_rows * self.board_cols
        self.perc_board: List[List[float | None]] = [
            [mines / tiles for _ in range(self.board_cols)]
            for _ in range(self.board_rows)
        ]
        self.reset()

    def reset(self):
        self.board = [
            [None for _ in range(self.board_cols)] for _ in range(self.board_rows)
        ]

    def find_safe_moves(self):
        save_moves = set()
        for i, row in enumerate(self.board):
            for j, val in enumerate(row):
                if val is not None and val > 0:
                    num, moves = self.surrounding(i, j)

                    if num > 0 and num == len(moves):
                        for r, c in moves:
                            self.board[r][c] = -1
                            self.mines_found += 1
                    elif num == 0:
                        save_moves |= set(moves)

        return save_moves

    def get_unmarked(self):
        return [
            (i, j)
            for i, row in enumerate(self.board)
            for j, col in enumerate(row)
            if col is None
        ]

    def surrounding(self, row, col) -> Tuple[int, List[Tuple[int, int]]]:
        num = self.board[row][col]
        possible_moves = []
        for i in range(-1, 2):
            for j in range(-1, 2):
                if (
                    (i == 0 and j == 0)
                    or not (0 <= (row + i) < self.board_rows)
                    or not (0 <= (col + j) < self.board_cols)
                ):
                    continue

                val = self.board[row + i][col + j]
                if val is None:
                    possible_moves.append((row + i, col + j))

                if val == -1:
                    num -= 1

        return num, possible_moves

    def probability(self):
        directions = [
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ]

        for i, row in enumerate(self.board):
            for j, val in enumerate(row):
                if val is not None:
                    self.perc_board[i][j] = None
                    continue

                bomb_count = 0
                unknown_count = 0
                for dr, dc in directions:
                    nr, nc = i + dr, j + dc
                    if (
                        not (0 <= nr < self.board_rows and 0 <= nc < self.board_cols)
                        or self.board[nr][nc] is None
                        or self.board[nr][nc] <= 0
                    ):
                        continue

                    n, moves = self.surrounding(nr, nc)
                    bomb_count += n
                    unknown_count += len(moves)

                self.perc_board[i][j] = (
                    bomb_count / unknown_count if unknown_count else 1
                )

        min_prob = float("inf")
        min_indices = []

        for r, row in enumerate(self.perc_board):
            for c, val in enumerate(row):
                if val is not None and val < min_prob:
                    min_prob = val
                    min_indices = [(r, c)]
                elif val == min_prob:
                    min_indices.append((r, c))

        return min_indices

    async def update_board(self, page: Page):
        selector = parsel.Selector(await page.inner_html("#Gra"))

        cells = await page.query_selector_all(f"#Gra img")
        self.raw_board = list(batched(cells, self.board_cols))
        try:
            for i in range(self.board_rows):
                for j in range(self.board_cols):
                    if self.board[i][j] is not None:
                        continue

                    cell = selector.css(f"#{i}-{j}")
                    img = cell.attrib["src"]

                    if not img:
                        continue

                    if "ptaszek" in img:
                        raise WinException("Wygrana!")
                    elif any(x in img for x in ["mineszary", "flagziel"]):
                        raise LostException("Przegrana (mina/koniec)")
                    elif "flag" in img:
                        self.board[i][j] = -1
                    elif "0.jpg" in img:
                        self.board[i][j] = 0
                    elif "1.jpg" in img:
                        self.board[i][j] = 1
                    elif "2.jpg" in img:
                        self.board[i][j] = 2
                    elif "3.jpg" in img:
                        self.board[i][j] = 3
                    elif "4.jpg" in img:
                        self.board[i][j] = 4
                    elif "5.jpg" in img:
                        self.board[i][j] = 5
                    elif "6.jpg" in img:
                        self.board[i][j] = 6
                    elif "7.jpg" in img:
                        self.board[i][j] = 7
                    elif "8.jpg" in img:
                        self.board[i][j] = 8
                    elif "9.jpg" in img:
                        raise LostException("Mina!!!")
        except WinException as e:
            raise e
        except LostException as e:
            raise e
        except Exception as e:
            print("Błąd update_board:", e)
            raise LostException(e)

    async def click(self, row, col, page: Page):
        await self.raw_board[row][col].click()

    def save_state(self, filename: str = "state.txt"):
        with open(filename, "w") as f:
            for row in self.board:
                line = ""
                for val in row:
                    if val is None:
                        line += "E "
                    elif val == -1:
                        line += "X "
                    elif val == 0:
                        line += "  "
                    else:
                        line += f"{val} "
                f.write(line.strip() + "\n")
