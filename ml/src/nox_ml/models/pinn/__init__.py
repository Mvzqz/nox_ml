"""Physics-informed neural network (PINN) plume: the network learns the 2D advection-diffusion kernel and is
the transport of the Bayesian inversion.

`params`, `equation` and `transport` need only numpy and scipy; `kernel`, `cache` and `model` need torch (the
``pinn`` extra), so nothing is imported here.
"""
