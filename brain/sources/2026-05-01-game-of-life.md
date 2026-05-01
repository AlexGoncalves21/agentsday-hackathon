# Source: Conway's Game of Life

## Input

- Original input file: `2026-05-01-game-of-life.md`

## Compiled Into

- [Conway's Game of Life](../concepts/conways-game-of-life.md)

## Information

Conway's Game of Life is a cellular automaton devised by mathematician John Horton Conway and popularized in 1970 through Martin Gardner's Mathematical Games column in Scientific American. It is called a game, but it is usually described as a zero-player game: after the initial state is set, the system evolves deterministically according to fixed rules.

The universe is a two-dimensional grid of cells. Each cell is either alive or dead. At each step, the state of a cell changes based on the number of live neighbors around it. Under the standard rules, live cells survive with two or three live neighbors, die by underpopulation with fewer than two, die by overpopulation with more than three, and dead cells become alive with exactly three live neighbors.

The surprising thing is that extremely simple local rules generate complex global behavior. Some patterns are stable, some oscillate, some move across the grid, and some create other patterns. Famous pattern categories include still lifes, oscillators, spaceships, gliders, and glider guns.

The Game of Life is important because it shows emergence, artificial life, complexity, and computation arising from simple rules. It is Turing complete, meaning that in principle it can simulate arbitrary computation. This makes it a canonical example in discussions of cellular automata, complexity theory, emergence, and bottom-up systems.

Useful concepts:

- cellular automaton
- local rules
- deterministic evolution
- emergence
- artificial life
- glider
- oscillator
- still life
- spaceship
- Turing completeness
- complex systems

Connections: Fibonacci also shows simple recurrence producing structure, but the Game of Life is spatial and rule-based rather than numerical. Monte Carlo and Markov systems are stochastic, while standard Game of Life is deterministic. Agent loops can borrow the general lesson that repeated local rules can produce large-scale structure, but they should not be described as cellular automata unless that model is actually used.

## Source URLs

- https://mathworld.wolfram.com/ConwaysGameofLife.html
- https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life
- https://conwaylife.com/wiki/Main_Page
- https://arxiv.org/abs/1407.1006
