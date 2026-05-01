# Monte Carlo and Markov Chains

## Information

Monte Carlo methods use random sampling to estimate quantities that are difficult or impossible to calculate exactly. They are useful when a problem has uncertainty, high dimensionality, complex integrals, or many possible outcomes. Instead of deriving a closed-form answer, a Monte Carlo method simulates many samples and uses aggregate results to approximate the answer.

Applications include physics simulations, finance, risk analysis, Bayesian inference, optimization, numerical integration, computer graphics, reliability analysis, and machine learning. The quality of a Monte Carlo estimate depends on the number of samples, the sampling method, variance, convergence behavior, and whether the simulation accurately represents the target problem.

A Markov process is a stochastic process where the future depends on the current state rather than the full history. This memoryless property is called the Markov property. A Markov chain consists of states and transition probabilities. After many transitions, some chains approach a stationary distribution.

Markov Chain Monte Carlo, or MCMC, combines these ideas. It constructs a Markov chain whose stationary distribution is the target distribution one wants to sample from. This is powerful in Bayesian statistics because posterior distributions are often difficult to sample directly. Important MCMC methods include Metropolis-Hastings and Gibbs sampling.

Key concepts:

- random sampling
- simulation
- stochastic process
- Markov property
- transition matrix
- stationary distribution
- burn-in
- convergence
- posterior distribution
- Metropolis-Hastings
- Gibbs sampling
- Bayesian inference

For agent systems, these ideas can be used metaphorically and sometimes technically. Agent state can be modeled as transitions; repeated critique/repair loops can be analyzed as convergence processes; uncertainty can be estimated through repeated samples or multiple independent agent passes. But this should not be overstated: many agent loops are not formal Markov chains unless their state and transition assumptions are explicitly defined.

## Sources

- https://www.britannica.com/science/Monte-Carlo-method
- https://www.britannica.com/science/probability-theory/Markovian-processes
- https://en.wikipedia.org/wiki/Markov_chain_Monte_Carlo
- https://arxiv.org/abs/2204.10145

