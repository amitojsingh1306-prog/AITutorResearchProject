# Exact LoCoMo questions used for the reported results

Source run: `20261108_live_budget`. These are the actual 49 questions, not newly generated examples.

Each question was asked in buffer, summary, vector and graph mode, with three trials per mode: 49 x 4 x 3 = 588 predictions. The source histories were loaded before asking these questions.

Category counts: 10 multi-hop, 10 temporal, 9 open-domain, 10 single-hop, 10 adversarial.

Scores below are saved-score means across three trials. For categories 1-4 the score is upstream answer F1; for category 5 it is the upstream binary abstention phrase score. Request time is local generation time. Context time is measured separately. Neither includes corpus ingestion.

Adversarial questions have no reference answer in this saved run. A blank reference is expected; the scorer awards 1 when the output contains "no information available" or "not mentioned", otherwise 0.

## 01. When did Caroline go to the LGBTQ support group?

**Source:** conv-26, QA index 0 (zero-based). **Category:** Temporal.

**Reference:** 7 May 2023

**Annotated evidence IDs:** D1:3

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 505.32 | 4.40 |
| summary | 0.0000 | 1459.48 | 61.13 |
| vector | 0.0000 | 4078.04 | 630.25 |
| graph | 0.0000 | 3934.00 | 350.41 |

## 02. What fields would Caroline be likely to pursue in her educaton?

**Source:** conv-26, QA index 2 (zero-based). **Category:** Open-domain.

**Reference:** Psychology, counseling certification

**Annotated evidence IDs:** D1:9, D1:11

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0451 | 1235.50 | 3.96 |
| summary | 0.0684 | 7364.96 | 81.67 |
| vector | 0.3636 | 4403.87 | 939.10 |
| graph | 0.0495 | 10954.05 | 1091.24 |

## 03. What did Caroline research?

**Source:** conv-26, QA index 3 (zero-based). **Category:** Multi-hop.

**Reference:** Adoption agencies

**Annotated evidence IDs:** D2:8

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 283.39 | 11.05 |
| summary | 0.0000 | 1413.61 | 84.40 |
| vector | 0.0000 | 8323.49 | 843.52 |
| graph | 0.0000 | 4179.29 | 394.53 |

## 04. What did the charity race raise awareness for?

**Source:** conv-26, QA index 82 (zero-based). **Category:** Single-hop.

**Reference:** mental health

**Annotated evidence IDs:** D2:2

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 416.80 | 19.93 |
| summary | 0.0580 | 2063.55 | 130.95 |
| vector | 0.4444 | 4676.49 | 682.44 |
| graph | 0.0000 | 954.07 | 322.16 |

## 05. What did Caroline realize after her charity race?

**Source:** conv-26, QA index 152 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D2:3

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 2191.09 | 23.47 |
| summary | 0.0000 | 7614.39 | 155.67 |
| vector | 0.0000 | 6700.56 | 1357.39 |
| graph | 0.0000 | 5321.01 | 293.20 |

## 06. When Jon has lost his job as a banker?

**Source:** conv-30, QA index 0 (zero-based). **Category:** Temporal.

**Reference:** 19 January, 2023

**Annotated evidence IDs:** D1:2

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 2159.40 | 50.53 |
| summary | 0.0000 | 2372.60 | 248.84 |
| vector | 0.0000 | 2624.77 | 1459.70 |
| graph | 0.0000 | 1957.61 | 304.22 |

## 07. How do Jon and Gina both like to destress?

**Source:** conv-30, QA index 2 (zero-based). **Category:** Single-hop.

**Reference:** by dancing

**Annotated evidence IDs:** D1:7, D1:6

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0784 | 1959.34 | 51.86 |
| summary | 0.0501 | 7782.81 | 99.48 |
| vector | 0.0680 | 8350.70 | 942.11 |
| graph | 0.2485 | 1495.41 | 347.63 |

## 08. What do Jon and Gina both have in common?

**Source:** conv-30, QA index 3 (zero-based). **Category:** Multi-hop.

**Reference:** They lost their jobs and decided to start their own businesses.

**Annotated evidence IDs:** D1:2, D1:3, D1:4, D2:1

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 1488.86 | 69.73 |
| summary | 0.0000 | 1359.98 | 50.56 |
| vector | 0.0000 | 3244.44 | 949.16 |
| graph | 0.0615 | 6253.48 | 359.62 |

## 09. What temporary job did Jon take to cover expenses?

**Source:** conv-30, QA index 79 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D18:2

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 1515.15 | 77.06 |
| summary | 1.0000 | 1095.76 | 55.85 |
| vector | 0.0000 | 4257.42 | 865.03 |
| graph | 0.0000 | 2151.09 | 403.37 |

## 10. Who did Maria have dinner with on May 3, 2023?

**Source:** conv-41, QA index 0 (zero-based). **Category:** Temporal.

**Reference:** her mother

**Annotated evidence IDs:** D13:16

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 1864.09 | 346.15 |
| summary | 0.0000 | 2735.85 | 126.90 |
| vector | 0.1667 | 6158.90 | 1353.35 |
| graph | 0.0000 | 2764.03 | 341.15 |

## 11. What martial arts has John done?

**Source:** conv-41, QA index 2 (zero-based). **Category:** Multi-hop.

**Reference:** Kickboxing, Taekwondo

**Annotated evidence IDs:** D2:28, D1:4

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 4937.73 | 59.34 |
| summary | 0.0000 | 975.65 | 69.02 |
| vector | 0.2000 | 3793.78 | 1063.53 |
| graph | 0.0000 | 765.57 | 294.70 |

## 12. What might John's financial status be?

**Source:** conv-41, QA index 8 (zero-based). **Category:** Open-domain.

**Reference:** Middle-class or wealthy

**Annotated evidence IDs:** D5:5

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 812.37 | 87.36 |
| summary | 0.0000 | 6988.71 | 365.63 |
| vector | 0.0000 | 12954.59 | 1494.65 |
| graph | 0.0333 | 5299.85 | 216.57 |

## 13. What is John's main focus in local politics?

**Source:** conv-41, QA index 65 (zero-based). **Category:** Single-hop.

**Reference:** Improving education and infrastructure

**Annotated evidence IDs:** D1:8

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 999.83 | 99.19 |
| summary | 0.0000 | 1040.26 | 80.74 |
| vector | 0.3750 | 3821.60 | 1370.72 |
| graph | 0.0816 | 10309.49 | 378.89 |

## 14. What is John's main focus in international politics?

**Source:** conv-41, QA index 152 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D1:8

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 1024.88 | 117.13 |
| summary | 0.3333 | 8284.74 | 100.62 |
| vector | 1.0000 | 4234.78 | 819.27 |
| graph | 1.0000 | 668.14 | 726.88 |

## 15. Is it likely that Nate has friends besides Joanna?

**Source:** conv-42, QA index 0 (zero-based). **Category:** Open-domain.

**Reference:** Yesteammates on hisvideo game team.

**Annotated evidence IDs:** D1:7

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 2051.93 | 37.56 |
| summary | 0.0452 | 10711.49 | 77.09 |
| vector | 0.0481 | 10131.17 | 515.00 |
| graph | 0.0403 | 11388.78 | 581.31 |

## 16. What kind of interests do Joanna and Nate share?

**Source:** conv-42, QA index 1 (zero-based). **Category:** Multi-hop.

**Reference:** Watching movies, making desserts

**Annotated evidence IDs:** D1:10, D1:11, D1:12, D3:4, D4:9, D10:9, D20:2

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 8030.70 | 505.13 |
| summary | 0.0000 | 5441.02 | 45.14 |
| vector | 0.5101 | 8049.58 | 1339.02 |
| graph | 0.0000 | 11664.36 | 511.14 |

## 17. When did Joanna first watch "Eternal Sunshine of the Spotless Mind?

**Source:** conv-42, QA index 2 (zero-based). **Category:** Temporal.

**Reference:** 2019

**Annotated evidence IDs:** D1:18

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 803.79 | 160.64 |
| summary | 0.0000 | 620.25 | 32.88 |
| vector | 0.0000 | 3557.00 | 755.67 |
| graph | 0.0000 | 552.77 | 121.41 |

## 18. What is one of Joanna's favorite movies?

**Source:** conv-42, QA index 88 (zero-based). **Category:** Single-hop.

**Reference:** "Eternal Sunshineof the Spotless Mind"

**Annotated evidence IDs:** D1:18, D, D1:20

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 321.69 | 27.89 |
| summary | 0.0000 | 449.94 | 32.25 |
| vector | 0.0000 | 3203.24 | 599.78 |
| graph | 0.0000 | 442.11 | 117.83 |

## 19. What color did Joanna choose for her hair?

**Source:** conv-42, QA index 199 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D7:1, D7:3

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 394.31 | 43.17 |
| summary | 1.0000 | 598.05 | 40.54 |
| vector | 1.0000 | 3120.91 | 672.07 |
| graph | 1.0000 | 358.89 | 618.41 |

## 20. what are John's goals with regards to his basketball career?

**Source:** conv-43, QA index 0 (zero-based). **Category:** Multi-hop.

**Reference:** improve shooting percentage, win a championship

**Annotated evidence IDs:** D1:9, D6:15, D11:17

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0152 | 6623.49 | 30.79 |
| summary | 0.0422 | 6850.06 | 78.16 |
| vector | 0.0986 | 6708.39 | 376.61 |
| graph | 0.1875 | 2017.26 | 299.59 |

## 21. Would Tim enjoy reading books by C. S. Lewis or John Greene?

**Source:** conv-43, QA index 3 (zero-based). **Category:** Open-domain.

**Reference:** C. S.Lewis

**Annotated evidence IDs:** D1:14, D1:16, D1:18

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0668 | 4910.23 | 63.72 |
| summary | 0.0579 | 7471.89 | 50.49 |
| vector | 0.0386 | 12181.49 | 442.67 |
| graph | 0.0000 | 2433.86 | 166.57 |

## 22. In which month's game did John achieve a career-high score in points?

**Source:** conv-43, QA index 6 (zero-based). **Category:** Temporal.

**Reference:** June 2023

**Annotated evidence IDs:** D3:1

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 584.87 | 41.34 |
| summary | 0.0000 | 791.64 | 106.69 |
| vector | 0.0000 | 6558.63 | 537.39 |
| graph | 0.0000 | 365.59 | 145.37 |

## 23. Which team did John sign with on 21 May, 2023?

**Source:** conv-43, QA index 71 (zero-based). **Category:** Single-hop.

**Reference:** The Minnesota Wolves

**Annotated evidence IDs:** D1:5

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 473.97 | 42.75 |
| summary | 0.0000 | 716.14 | 107.15 |
| vector | 0.0000 | 4338.13 | 589.87 |
| graph | 0.0000 | 4045.78 | 387.11 |

## 24. Which team did Tim sign with on 21 May, 2023?

**Source:** conv-43, QA index 178 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D1:5

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 437.96 | 27.82 |
| summary | 1.0000 | 626.97 | 103.58 |
| vector | 0.0000 | 4299.32 | 528.00 |
| graph | 1.0000 | 487.86 | 135.90 |

## 25. Which year did Audrey adopt the first three of her dogs?

**Source:** conv-44, QA index 0 (zero-based). **Category:** Temporal.

**Reference:** 2020

**Annotated evidence IDs:** D1:7

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 1422.51 | 87.55 |
| summary | 0.0000 | 5434.29 | 74.76 |
| vector | 0.0000 | 3009.00 | 465.31 |
| graph | 0.0000 | 2108.68 | 271.65 |

## 26. What kind of indoor activities has Andrew pursued with his girlfriend?

**Source:** conv-44, QA index 2 (zero-based). **Category:** Multi-hop.

**Reference:** boardgames, volunteering at pet shelter, wine tasting, growing flowers

**Annotated evidence IDs:** D13:1, D23:1, D25:1, D19:15

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 549.41 | 41.74 |
| summary | 0.0000 | 1066.44 | 168.68 |
| vector | 0.0000 | 6503.79 | 452.96 |
| graph | 0.0250 | 9590.90 | 380.84 |

## 27. What is an indoor activity that Andrew would enjoy doing while make his dog happy?

**Source:** conv-44, QA index 19 (zero-based). **Category:** Open-domain.

**Reference:** cook dog treats

**Annotated evidence IDs:** D10:12, D12:1

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 3279.12 | 39.23 |
| summary | 0.0619 | 5048.75 | 115.60 |
| vector | 0.0000 | 6717.83 | 500.45 |
| graph | 0.0429 | 9231.09 | 1472.52 |

## 28. Which specific type of bird mesmerizes Andrew?

**Source:** conv-44, QA index 61 (zero-based). **Category:** Single-hop.

**Reference:** Eagles

**Annotated evidence IDs:** D1:16

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 559.41 | 43.67 |
| summary | 0.0000 | 2001.60 | 89.32 |
| vector | 1.0000 | 3032.23 | 614.04 |
| graph | 0.0000 | 3008.07 | 363.69 |

## 29. Which specific type of bird mesmerizes Audrey?

**Source:** conv-44, QA index 123 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D1:16

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 957.71 | 157.43 |
| summary | 1.0000 | 485.34 | 39.88 |
| vector | 1.0000 | 2793.73 | 282.39 |
| graph | 0.0000 | 17231.15 | 585.98 |

## 30. What are John's suspected health problems?

**Source:** conv-47, QA index 0 (zero-based). **Category:** Open-domain.

**Reference:** Obesity

**Annotated evidence IDs:** D1:27

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 2143.98 | 70.99 |
| summary | 0.0000 | 1757.62 | 65.38 |
| vector | 0.0000 | 2143.26 | 631.36 |
| graph | 0.0000 | 1656.54 | 1304.81 |

## 31. Which recreational activity was James pursuing on March 16, 2022?

**Source:** conv-47, QA index 1 (zero-based). **Category:** Temporal.

**Reference:** bowling

**Annotated evidence IDs:** D1:26

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 332.51 | 237.55 |
| summary | 0.0000 | 400.77 | 87.52 |
| vector | 0.0000 | 2760.00 | 523.29 |
| graph | 0.0000 | 5245.77 | 507.59 |

## 32. Which places or events have John and James planned to meet at?

**Source:** conv-47, QA index 2 (zero-based). **Category:** Multi-hop.

**Reference:** VR Club, McGee's, baseball game

**Annotated evidence IDs:** D1:36, D21:15, D23:5, D23:6

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 3130.08 | 66.59 |
| summary | 0.0000 | 819.30 | 57.50 |
| vector | 0.0000 | 5114.78 | 882.28 |
| graph | 0.0000 | 6697.04 | 1238.69 |

## 33. What programming languages has James worked with?

**Source:** conv-47, QA index 67 (zero-based). **Category:** Single-hop.

**Reference:** Python and C++

**Annotated evidence IDs:** D1:8

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 512.61 | 34.60 |
| summary | 0.0000 | 476.31 | 44.04 |
| vector | 0.5000 | 2541.11 | 938.70 |
| graph | 0.0000 | 9665.94 | 318.80 |

## 34. What did John adopt in April 2022?

**Source:** conv-47, QA index 150 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D5:1

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 371.59 | 27.27 |
| summary | 1.0000 | 413.85 | 50.89 |
| vector | 1.0000 | 1482.28 | 450.69 |
| graph | 1.0000 | 567.22 | 138.00 |

## 35. What kind of project was Jolene working on in the beginning of January 2023?

**Source:** conv-48, QA index 0 (zero-based). **Category:** Temporal.

**Reference:** electricity engineering project

**Annotated evidence IDs:** D1:2

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 922.82 | 24.56 |
| summary | 0.0000 | 1449.55 | 79.86 |
| vector | 0.0521 | 9564.72 | 987.24 |
| graph | 0.0485 | 9347.00 | 176.27 |

## 36. Which of Deborah`s family and friends have passed away?

**Source:** conv-48, QA index 1 (zero-based). **Category:** Multi-hop.

**Reference:** mother, father, her friend Karlie

**Annotated evidence IDs:** D1:5, D2:1, D6:4

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 418.93 | 69.22 |
| summary | 0.0000 | 439.14 | 38.74 |
| vector | 0.1796 | 3416.72 | 805.35 |
| graph | 0.0000 | 540.40 | 282.43 |

## 37. In what country did Jolene's mother buy her the pendant?

**Source:** conv-48, QA index 5 (zero-based). **Category:** Open-domain.

**Reference:** In France

**Annotated evidence IDs:** D1:8

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 387.72 | 26.56 |
| summary | 0.0000 | 391.73 | 531.66 |
| vector | 0.0000 | 2154.90 | 822.24 |
| graph | 0.0000 | 364.86 | 106.46 |

## 38. What pets does Jolene have?

**Source:** conv-48, QA index 15 (zero-based). **Category:** Single-hop.

**Reference:** snakes

**Annotated evidence IDs:** D2:20, D2:22, D2:24

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 399.98 | 25.08 |
| summary | 0.0000 | 563.28 | 68.04 |
| vector | 0.0000 | 3056.70 | 460.55 |
| graph | 0.0000 | 328.36 | 82.58 |

## 39. What are the names of Deborah's snakes?

**Source:** conv-48, QA index 191 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D2:20, D2:22

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 409.49 | 28.04 |
| summary | 1.0000 | 456.45 | 50.81 |
| vector | 1.0000 | 2425.80 | 783.54 |
| graph | 1.0000 | 2230.34 | 757.78 |

## 40. What kind of car does Evan drive?

**Source:** conv-49, QA index 0 (zero-based). **Category:** Multi-hop.

**Reference:** Prius

**Annotated evidence IDs:** D1:2, D1:4, D18:1, D18:3, D22:2

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 958.46 | 32.51 |
| summary | 0.0000 | 1312.16 | 77.69 |
| vector | 0.4333 | 3145.20 | 366.33 |
| graph | 0.0000 | 2480.89 | 307.63 |

## 41. Which hobby did Sam take up in May 2023?

**Source:** conv-49, QA index 4 (zero-based). **Category:** Temporal.

**Reference:** painting

**Annotated evidence IDs:** D1:11

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 624.36 | 34.66 |
| summary | 0.0000 | 463.49 | 43.23 |
| vector | 0.2500 | 3425.41 | 446.80 |
| graph | 0.0000 | 12446.50 | 578.33 |

## 42. Which country was Evan visiting in May 2023?

**Source:** conv-49, QA index 5 (zero-based). **Category:** Open-domain.

**Reference:** Canada

**Annotated evidence IDs:** D2:1

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 347.13 | 22.82 |
| summary | 0.0000 | 363.09 | 32.78 |
| vector | 1.0000 | 2431.52 | 531.42 |
| graph | 0.0000 | 17671.05 | 1125.49 |

## 43. What type of car did Evan get after his old Prius broke down?

**Source:** conv-49, QA index 83 (zero-based). **Category:** Single-hop.

**Reference:** new Prius

**Annotated evidence IDs:** D1:2

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 367.86 | 31.21 |
| summary | 0.0000 | 402.32 | 32.96 |
| vector | 0.3077 | 4005.73 | 917.58 |
| graph | 0.1429 | 4381.31 | 966.59 |

## 44. What type of car did Sam get after his old Prius broke down?

**Source:** conv-49, QA index 156 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D1:2

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 400.45 | 34.21 |
| summary | 1.0000 | 319.15 | 28.15 |
| vector | 0.0000 | 3221.33 | 621.30 |
| graph | 0.0000 | 1319.73 | 484.64 |

## 45. When did Calvin first travel to Tokyo?

**Source:** conv-50, QA index 0 (zero-based). **Category:** Temporal.

**Reference:** between 26 March and 20 April 2023

**Annotated evidence IDs:** D3:1

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 1398.92 | 31.36 |
| summary | 0.0000 | 2152.34 | 234.46 |
| vector | 0.0392 | 3304.10 | 799.55 |
| graph | 0.0000 | 1189.92 | 148.28 |

## 46. What items did Calvin buy in March 2023?

**Source:** conv-50, QA index 1 (zero-based). **Category:** Multi-hop.

**Reference:** mansion in Japan, luxury car Ferrari 488 GTB

**Annotated evidence IDs:** D1:3, D2:1

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 962.58 | 92.77 |
| summary | 0.0000 | 915.24 | 111.45 |
| vector | 0.0476 | 4031.80 | 483.92 |
| graph | 0.0000 | 349.77 | 109.08 |

## 47. Which country do Calvin and Dave want to meet in?

**Source:** conv-50, QA index 4 (zero-based). **Category:** Open-domain.

**Reference:** United States

**Annotated evidence IDs:** D3:9, D3:10

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 301.63 | 37.76 |
| summary | 0.0000 | 649.55 | 96.15 |
| vector | 0.0000 | 2429.01 | 433.99 |
| graph | 0.0000 | 2578.11 | 109.83 |

## 48. How long did Calvin plan to stay in Japan?

**Source:** conv-50, QA index 71 (zero-based). **Category:** Single-hop.

**Reference:** A few months

**Annotated evidence IDs:** D1:15

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 0.0000 | 888.61 | 60.78 |
| summary | 0.0000 | 620.21 | 53.95 |
| vector | 0.2611 | 3437.85 | 402.83 |
| graph | 0.0000 | 469.46 | 102.00 |

## 49. Which DJ was Dave's favorite at the music festival in April 2023?

**Source:** conv-50, QA index 158 (zero-based). **Category:** Adversarial / abstention.

**Reference:** Unsupported question: apply abstention rule.

**Annotated evidence IDs:** D2:10

| Mode | Mean score | Mean request ms | Mean context ms |
|---|---:|---:|---:|
| buffer | 1.0000 | 1099.67 | 78.32 |
| summary | 1.0000 | 910.38 | 111.23 |
| vector | 1.0000 | 2998.96 | 532.78 |
| graph | 1.0000 | 364.30 | 92.87 |
