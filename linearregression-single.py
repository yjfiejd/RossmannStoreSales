"""
Private Score: 0.42820, Public Score: 0.42460
"""

import datetime as dt

import pandas as pd
from pandas import Series, DataFrame
import numpy as np

from sklearn.linear_model import LinearRegression

pd.options.mode.chained_assignment = None


################################################################
# Import CSV Data into Pandas DataFrames                       #
################################################################
training_df = pd.read_csv("data/train.csv")
store_df = pd.read_csv("data/store.csv")
test_df = pd.read_csv("data/test.csv")

# print(training_df.head())
# print(store_df.head())
# print(test_df.head())


################################################################
# Process Data (Universal)                                     #
################################################################

def is_nan(val):
    return val != val


def less_than_ten(val):
    if int(val) < 10:
        return "0" + val
    else:
        return val

############################################
# training_df & test_df                    #
############################################

# Fill NaN values in test_df with Open = 1 if DayOfWeek != 7
test_df["Open"][is_nan(test_df["Open"])] = (test_df["DayOfWeek"] != 7).astype(int)

# Create "Year" & "Month" columns
training_df["Year"] = training_df["Date"].apply(lambda x: dt.datetime.strptime(x, "%Y-%m-%d").year)
training_df["Month"] = training_df["Date"].apply(lambda x: dt.datetime.strptime(x, "%Y-%m-%d").month)

test_df["Year"] = test_df["Date"].apply(lambda x: dt.datetime.strptime(x, "%Y-%m-%d").year)
test_df["Month"] = test_df["Date"].apply(lambda x: dt.datetime.strptime(x, "%Y-%m-%d").month)

# Create "YearMonth" column
training_df["YearMonth"] = training_df["Date"].apply(lambda x: str(dt.datetime.strptime(x, "%Y-%m-%d").year) + "-" + less_than_ten(str(dt.datetime.strptime(x, "%Y-%m-%d").month)))
test_df["YearMonth"] = test_df["Date"].apply(lambda x: str(dt.datetime.strptime(x, "%Y-%m-%d").year) + "-" + less_than_ten(str(dt.datetime.strptime(x, "%Y-%m-%d").month)))

# "StateHoliday" has values "0" & 0
training_df["StateHoliday"].loc[training_df["StateHoliday"] == 0] = "0"
test_df["StateHoliday"].loc[test_df["StateHoliday"] == 0] = "0"

# Create "StateHolidayBinary" column
# training_df["StateHolidayBinary"] = training_df["StateHoliday"].map({0: 0, "0": 0, "a": 1, "b": 1, "c": 1})
# test_df["StateHolidayBinary"] = test_df["StateHoliday"].map({0: 0, "0": 0, "a": 1, "b": 1, "c": 1})

# One-hot encoding of "DayOfWeek" & "StateHoliday" columns
training_df = pd.get_dummies(training_df, columns=["DayOfWeek", "StateHoliday"])
test_df = pd.get_dummies(test_df, columns=["DayOfWeek", "StateHoliday"])

############################################
# store_df                                 #
############################################

# Fill NaN values in store_df for "CompetitionDistance" = 0 (since no record exists where "CD" = NaN & "COS[Y/M]" = !NaN)
store_df["CompetitionDistance"][is_nan(store_df["CompetitionDistance"])] = 0

# Fill NaN values in store_df for "CompetitionSince[X]" with 1900-01
store_df["CompetitionOpenSinceYear"][(store_df["CompetitionDistance"] != 0) & (is_nan(store_df["CompetitionOpenSinceYear"]))] = 1900
store_df["CompetitionOpenSinceMonth"][(store_df["CompetitionDistance"] != 0) & (is_nan(store_df["CompetitionOpenSinceMonth"]))] = 1

# One-hot encoding of "StoreType" & "Assortment" columns
store_df = pd.get_dummies(store_df, columns=["StoreType", "Assortment"])


################################################################
# Process Data (Custom)                                        #
################################################################

# Drop "StateHolidayBinary" as "StateHoliday_[X]" Exists
# training_df.drop(["StateHolidayBinary"], axis=1, inplace=True)
# test_df.drop(["StateHolidayBinary"], axis=1, inplace=True)

# Remove rows for stores not in test_df
training_df = training_df[training_df["Store"].isin(test_df.Store.unique())]
store_df = store_df[store_df["Store"].isin(test_df.Store.unique())]

# Remove all Closed Stores ("Sales" = 0)
training_df = training_df[training_df["Open"] != 0]

# Drop Unnecessary Columns from training_df (not useful for prediction)
training_df.drop(["Open", "Customers"], axis=1, inplace=True)

# Save IDs of Closed Stores ("Sales" = 0 assigned later) & Remove Rows
closed_store_ids = test_df["Id"][test_df["Open"] == 0].values
test_df = test_df[test_df["Open"] != 0]

# Drop Unnecessary Columns from test_df (not useful for prediction)
test_df.drop(["Open"], axis=1, inplace=True)

# Drop "Date" column
training_df.drop(["Date"], axis=1, inplace=True)
test_df.drop(["Date"], axis=1, inplace=True)

# Drop "Year", "Month" & "YearMonth" as test_df only has "Year" = 2015 & "Month" = 8 || 9
training_df.drop(["Year", "Month", "YearMonth"], axis=1, inplace=True)
test_df.drop(["Year", "Month", "YearMonth"], axis=1, inplace=True)

# Drop "CompetitionOpenSinceYear", "CompetitionOpenSinceMonth", "Promo2", "Promo2SinceYear" & "Promo2SinceWeek" (not useful for prediction)
store_df.drop(["CompetitionOpenSinceYear", "CompetitionOpenSinceMonth", "Promo2", "Promo2SinceYear", "Promo2SinceWeek", "PromoInterval"], axis=1, inplace=True)

# Create new DataFrames merging store_df
training_df = pd.merge(training_df, store_df, on="Store")
test_df = pd.merge(test_df, store_df, on="Store")


################################################################
# RMSPE Function                                               #
################################################################

def rmspe(y_true, y_pred):
    w = np.zeros(y_true.shape, dtype=float)
    index = y_true != 0
    w[index] = 1.0 / (y_true[index])
    diff = y_true - y_pred
    diff_percentage = diff * w
    diff_percentage_squared = diff_percentage ** 2
    rmspe = np.sqrt(np.mean(diff_percentage_squared))
    return rmspe


################################################################
# Training the Model & Predicting Sales                        #
################################################################

"""
A linear regression model for all stores.

Features: Store, Promo, SchoolHoliday, DayOfWeek (one-hot encoded), StateHoliday (one-hot encoded), CompetitionDistance, StoreType (one-hot encoded), Assortment (one-hot encoded)

Assumptions:
- Stores that are not in the test data will not affect the values for other stores in the test data.
- The Year-Month has no effect on the sales as testing data is only for 2015-08 & 2015-09.
- The store's opening/closing dates does not affect the store's performance. For example, a store that was closed yesterday will not get more sales today because of that.
- The competition of each store will affect it consistently, hence, it does not matter when the competition started.
"""

print("Making predictions...")

predictions = Series()

X_train = training_df.drop(["Sales"], axis=1)
Y_train = training_df["Sales"]
X_test = test_df.copy()

lreg = LinearRegression()
lreg.fit(X_train, Y_train)

store_ids = X_test["Id"]
X_test.drop(["Id"], axis=1, inplace=True)
X_test = X_test.reindex(columns=X_train.columns, fill_value=0)
Y_pred = lreg.predict(X_test)

predictions = predictions.append(Series(Y_pred, index=store_ids))
predictions = predictions.append(Series(0, index=closed_store_ids))

submission = pd.DataFrame({"Id": predictions.index, "Sales": predictions.values})
submission.to_csv("predictions/linearregression4.csv", index=False)

print("Predictions saved.")
