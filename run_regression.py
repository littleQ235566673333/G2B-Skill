# Monthly yields for July 1953 through June 1956 (months 1–36)
yields = [
    3.25, # 1953-Jul
    3.22, # 1953-Aug
    3.19, # 1953-Sep
    3.06, # 1953-Oct
    3.04, # 1953-Nov
    2.96, # 1953-Dec
    2.90, # 1954-Jan
    2.85, # 1954-Feb
    2.73, # 1954-Mar
    2.70, # 1954-Apr
    2.72, # 1954-May
    2.70, # 1954-Jun
    2.62, # 1954-Jul
    2.60, # 1954-Aug
    2.64, # 1954-Sep
    2.65, # 1954-Oct
    2.68, # 1954-Nov
    2.68, # 1954-Dec
    2.77, # 1955-Jan
    2.92, # 1955-Feb
    2.92, # 1955-Mar
    2.92, # 1955-Apr
    3.03, # 1955-May
    2.98, # 1955-Jun
    2.96, # 1955-Jul
    3.02, # 1955-Aug
    3.00, # 1955-Sep
    2.96, # 1955-Oct
    2.96, # 1955-Nov
    2.97, # 1955-Dec
    2.94, # 1956-Jan
    2.93, # 1956-Feb
    2.98, # 1956-Mar
    3.10, # 1956-Apr
    3.03, # 1956-May
    2.98  # 1956-Jun
]

import numpy as np
from sklearn.linear_model import LinearRegression

X = np.arange(1, 37).reshape(-1, 1)  # 1-36 for months
y = np.array(yields)

model = LinearRegression()
model.fit(X, y)

# Predict for July 1956 (month 37)
y_pred = model.predict(np.array([[37]]))[0]

# Round to three decimals
result = round(float(y_pred), 3)

with open("results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/train/iter_3/task_oqa-100/r3/evolve_oqa-100/output.txt", "w") as f:
    f.write(f"{result}\n")
