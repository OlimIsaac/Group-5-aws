import os
import numpy as np

from django.utils import timezone
from .models import PressureFrame, User


LOW_PRESSURE_THRESHOLD = 1000  # example threshold
HIGH_PRESSURE_THRESHOLD = 3500
MIN_CLUSTER_SIZE = 10


def ingest_csv_for_user(user: User, csv_path: str):
    """Process a CSV containing timestamped 32x32 matrices for a given user."""
    import pandas as pd
    
    df = pd.read_csv(csv_path)
    # expect columns: timestamp, and then 1024 values or row-major representation
    for _, row in df.iterrows():
        timestamp = pd.to_datetime(row['timestamp'])
        # assume matrix stored as 1024 comma-separated str in 'matrix' column
        if 'matrix' in row:
            values = np.fromstring(row['matrix'], sep=',')
        else:
            # fallback: remaining columns represent flattened matrix
            values = row.drop('timestamp').values
        matrix = values.reshape((32, 32)).tolist()

        ppi, contact = compute_metrics(np.array(matrix))
        high_flag = ppi >= HIGH_PRESSURE_THRESHOLD

        PressureFrame.objects.create(
            user=user,
            timestamp=timestamp,
            raw_matrix=matrix,
            peak_pressure_index=ppi,
            contact_area_percentage=contact,
            high_pressure_flag=high_flag,
        )


def compute_metrics(matrix: np.ndarray):
    # identify clusters above zero pressure
    mask = matrix > 0
    # simple approach: label connected components
    from scipy.ndimage import label

    labeled, num = label(mask)
    max_pressure = 0
    for label_idx in range(1, num + 1):
        coords = np.argwhere(labeled == label_idx)
        if coords.shape[0] < MIN_CLUSTER_SIZE:
            continue
        cluster_vals = matrix[labeled == label_idx]
        max_pressure = max(max_pressure, cluster_vals.max())

    contact_area = (matrix > LOW_PRESSURE_THRESHOLD).sum() / matrix.size * 100
    return max_pressure, contact_area
