| run | model | role | loo_rmse_ppb | loo_bias_ppb | loo_hourly_rmse_ppb | r_tempo | sunday_ratio | sunday_ratio_gap | placebo_center | placebo_halfwidth | eligible | fit_seconds | predict_seconds | n_params |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kriging | kriging | reference | 10.33 | 5.16 | 8.95 | - | - | - | - | - | - | 0.00 | 0.38 | 0 |
| idw | idw | reference | 11.57 | 6.62 | 9.49 | - | - | - | - | - | - | 0.00 | 0.10 | 0 |
| pinn_puff_k1000 | pinn_puff | model | 11.80 | 4.96 | 10.71 | 0.85 | 0.47 (0.38-0.57) | 0.18 | 1.04 | 0.19 | yes | 721.42 | 0.11 | 12832 |
| pinn_puff.tempo | pinn_puff | model | 11.84 | 4.90 | 10.78 | 0.85 | 0.46 (0.36-0.55) | 0.19 | 1.02 | 0.18 | yes | 542.70 | 0.11 | 12832 |
| pinn_puff_k500 | pinn_puff | model | 11.86 | 5.17 | 10.67 | 0.84 | 0.49 (0.40-0.59) | 0.16 | 1.05 | 0.19 | yes | 679.81 | 0.10 | 12832 |
| pinn_puff | pinn_puff | model | 11.87 | 5.22 | 10.66 | 0.85 | 0.48 (0.36-0.62) | 0.17 | 1.01 | 0.12 | yes | 528.94 | 0.09 | 12832 |
| pinn_puff_oh | pinn_puff | model | 11.87 | 5.22 | 10.66 | 0.85 | 0.48 (0.36-0.62) | 0.17 | 1.01 | 0.12 | yes | 523.00 | 0.09 | 12832 |
| pinn_puff_k1500 | pinn_puff | model | 11.90 | 4.98 | 10.81 | 0.85 | 0.47 (0.38-0.57) | 0.18 | 1.02 | 0.20 | yes | 526.52 | 0.11 | 12832 |
| pinn_puff.transport | pinn_puff | model | 11.90 | 4.98 | 10.81 | 0.85 | 0.47 (0.38-0.57) | 0.18 | 1.02 | 0.20 | yes | 471.54 | 0.09 | 12832 |
| pinn_puff.kernel | pinn_puff | model | 12.08 | 5.19 | 10.91 | 0.85 | 0.47 (0.38-0.58) | 0.18 | 1.04 | 0.19 | yes | 445.14 | 0.09 | 19136 |
| pinn_plume | pinn_plume | model | 12.49 | 5.16 | 11.37 | 0.78 | 0.42 (0.33-0.54) | 0.23 | 1.09 | 0.33 | yes | 16.02 | 0.15 | 12832 |
| inversion_puff | inversion_puff | model | 12.50 | 5.61 | 11.17 | 0.84 | 0.52 (0.44-0.59) | 0.13 | 0.97 | 0.16 | yes | 322.57 | 0.10 | 31 |
| inversion_puff_tune | inversion_puff | model | 12.50 | 5.61 | 11.17 | 0.84 | 0.52 (0.44-0.59) | 0.13 | 0.97 | 0.16 | yes | 307.45 | 0.20 | 31 |
| pinn_puff_k3000 | pinn_puff | model | 12.60 | 5.73 | 11.22 | 0.84 | 0.47 (0.38-0.57) | 0.18 | 0.99 | 0.21 | yes | 685.47 | 0.12 | 12832 |
| regularized_ls | regularized_ls | model | 13.57 | 6.81 | 11.74 | 0.74 | 0.44 (0.37-0.55) | 0.21 | 1.08 | 0.35 | yes | 8.57 | 0.09 | 31 |
| lognormal_map | lognormal_map | model | 13.59 | 6.84 | 11.74 | 0.74 | 0.45 (0.44-0.46) | 0.20 | 1.08 | 0.34 | yes | 7.42 | 0.12 | 31 |
| baseline | inversion_plume | model | 13.59 | 6.83 | 11.75 | 0.74 | 0.42 (0.35-0.54) | 0.23 | 1.08 | 0.35 | yes | 9.49 | 0.14 | 31 |
| rf_deweather | rf_deweather | model | 14.61 | 8.27 | 12.05 | - | 0.53 (0.42-0.57) | 0.12 | 0.97 | 0.09 | yes | 1.01 | 0.05 | 381870 |
| normalized_ratio | normalized_ratio | model | 16.75 | 7.30 | 15.08 | - | 0.56 (0.46-0.71) | 0.09 | 0.88 | 0.22 | yes | 0.00 | 9.27 | 2 |
