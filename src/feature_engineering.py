import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler,LabelEncoder
import pickle
import os
import warnings
from dotenv import load_dotenv
warnings.filterwarnings("ignore")

load_dotenv()

DB_USER=os.getenv("DB_USER")
DB_PASSWORD=os.getenv("DB_PASSWORD")
DB_HOST=os.getenv("DB_HOST","localhost")
DB_PORT=int(os.getenv("DB_PORT",3306))
DB_NAME=os.getenv("DB_NAME")

RANDOM_STATE=42
TEST_SIZE=0.2
OUTPUT_DIR="outputs"

def get_engine():
    url=f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url,echo=False)

def load_data():
    print("Loading feature store from MySQL")
    engine=get_engine()
    df=pd.read_sql("Select * from feature_store",con=engine)
    print(f" Shape: {df.shape}")
    print(f" Churn rate: {df['churned'].mean()*100:.1f}%")
    return df

def cap_outliers(df:pd.DataFrame,cols:list):
    print("\n Capping Outliers(IQR METHOD)...")
    df=df.copy()
    for col in cols:
        Q1=df[col].quantile(0.25)
        Q3=df[col].quantile(0.75)
        IQR=Q3-Q1
        lower=Q1-1.5*IQR
        upper=Q3+1.5*IQR
        before=df[col].max()
        df[col]=df[col].clip(lower=lower,upper=upper)
        after=df[col].max()
        print(f" {col}:max{before:.1f}->{after:.1f}")
    return df

def encode_segment(df:pd.DataFrame):
    print("\n Encoding rfm segment")
    le=LabelEncoder()
    df=df.copy()
    df["rfm_segment_encoded"]=le.fit_transform(df["rfm_segment"])
    print(f" Classes:{list(le.classes_)}")
    return df,le

def select_features(df:pd.DataFrame):
    feature_cols = [
        # RFM raw (recency_days removed — it IS the churn label: recency > 90 = churned)
        "frequency",
        "monetary",
        "avg_order_value",

        # Behavioral
        "order_gap_std",
        "avg_order_gap_days",
        "unique_skus",
        "product_categories",

        # Trend
        "spend_trend_pct",
        "customer_lifespan_days",

        # RFM scores (r_score, rfm_total_score, rfm_segment_encoded removed — derived from recency_days)
        "f_score",
        "m_score",
    ]

    X = df[feature_cols]
    y = df["churned"]

    print(f"\nFeatures selected: {len(feature_cols)}")
    print(f"   {feature_cols}")
    return X, y, feature_cols


def split_data(X,y):
    print(f"Splitting data(80/20, stratified)....")
    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=TEST_SIZE,random_state=RANDOM_STATE)
    print(f"   Train: {X_train.shape[0]} rows | "
          f"Churn rate: {y_train.mean()*100:.1f}%")
    print(f"   Test : {X_test.shape[0]} rows  | "
          f"Churn rate: {y_test.mean()*100:.1f}%")
    return X_train,X_test,y_train,y_test

def scale_features(X_train,X_test):
    print("\n Scaling Features")

    scaler=StandardScaler()
    X_train_scaled=scaler.fit_transform(X_train)
    X_test_scaled=scaler.transform(X_test)
    print(f"   Mean of first feature (train): "
          f"{X_train_scaled[:, 0].mean():.4f} (should be ~0)")
    print(f"   Std  of first feature (train): "
          f"{X_train_scaled[:, 0].std():.4f}  (should be ~1)")
    return X_train_scaled, X_test_scaled, scaler

def save_artifacts(X_train,X_test,X_train_scaled,X_test_scaled,y_train,y_test,scaler,le,feature_cols):
    print("\n Saving artifacts to outputs folder..")
    os.makedirs(OUTPUT_DIR,exist_ok=True)

    artifacts={
        "X_train"        : X_train,
        "X_test"         : X_test,
        "X_train_scaled" : X_train_scaled,
        "X_test_scaled"  : X_test_scaled,
        "y_train"        : y_train,
        "y_test"         : y_test,
        "scaler"         : scaler,
        "label_encoder"  : le,
        "feature_cols"   : feature_cols
    }
    for name,obj in artifacts.items():
        path=os.path.join(OUTPUT_DIR,f"{name}.pkl")
        with open(path,"wb")as f:
            pickle.dump(obj,f)
        print(f" Saved:{path}")

if __name__=="__main__":
    print("=" * 60)
    print("  STEP 5: Feature Engineering")
    print("=" * 60)

    # Columns to cap outliers on
    outlier_cols = [
        "monetary", "avg_order_value", "frequency",
        "unique_skus", "customer_lifespan_days", "spend_trend_pct"
    ]

    df= load_data()
    df= cap_outliers(df, outlier_cols)
    df, le= encode_segment(df)
    X, y, feature_cols= select_features(df)
    X_train, X_test, y_train, y_test = split_data(X, y)
    X_train_scaled, X_test_scaled, scaler = scale_features(X_train, X_test)

    save_artifacts(
        X_train, X_test,
        X_train_scaled, X_test_scaled,
        y_train, y_test,
        scaler, le, feature_cols
    )

    print("\nStep 5 complete!")
    print("   outputs/ now has all train/test splits + scaler + encoder")
    print("   Next: run models.ipynb")

