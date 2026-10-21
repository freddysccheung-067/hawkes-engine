# Reference

The public names, as listed in `hawkes_engine.__all__`. Anything else is private
and may change without notice.

## Estimation

```{eval-rst}
.. autofunction:: hawkes_engine.fit

.. autoclass:: hawkes_engine.FitResult
   :members: to_dict, from_dict
```

## Likelihood

```{eval-rst}
.. autofunction:: hawkes_engine.loglik

.. autoclass:: hawkes_engine.LoglikResult
```

## Simulation

```{eval-rst}
.. autofunction:: hawkes_engine.simulate

.. autofunction:: hawkes_engine.simulate_many
```

## Diagnostics

```{eval-rst}
.. autofunction:: hawkes_engine.time_rescale

.. autofunction:: hawkes_engine.ks_test

.. autofunction:: hawkes_engine.qq_data

.. autofunction:: hawkes_engine.report
```

## Trust

```{eval-rst}
.. autofunction:: hawkes_engine.trust_lookup

.. autoclass:: hawkes_engine.MapAnswer
```

## Stability

```{eval-rst}
.. autofunction:: hawkes_engine.spectral_radius

.. autofunction:: hawkes_engine.stationary_mean
```
