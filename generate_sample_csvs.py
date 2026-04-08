#!/usr/bin/env python3
"""
generate_sample_csvs.py
=======================
Generates realistic Sensore pressure mat CSV files for testing the upload
feature.  Output matches the real hardware scale observed in
de0e9b2c_20251013.csv:

    0   = no sensor contact
    ~20 = lightest contact
    705 = maximum recorded pressure

The application normalises any uploaded CSV to the internal 0-4095 scale
automatically, so these files work with the upload page out of the box.

Usage:
    python generate_sample_csvs.py

Output:
    sample_data/
        patient_001_normal.csv         (60 frames, symmetric sitting)
        patient_002_left_lean.csv      (45 frames, gradual left asymmetry)
        patient_003_high_pressure.csv  (30 frames, high-pressure episode)
        format_b_sample.csv            (20 frames, Format B -- 1024 values/row)
"""
import os, math, random
import numpy as np

OUTPUT_DIR = 'sample_data'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Real hardware scale: 0-705 (matches de0e9b2c_20251013.csv)
HW_MAX = 705

def hw_scale(val):
    return max(0, min(HW_MAX, int(val * HW_MAX / 3200)))

def sitting_pattern(lean='none', intensity=1.0):
    grid = np.zeros((32, 32), dtype=np.float32)
    if lean == 'left':
        lc_x, lc_y, rc_x, rc_y = 9, 19, 20, 19
        l_i, r_i = intensity * 1.4, intensity * 0.6
    elif lean == 'right':
        lc_x, lc_y, rc_x, rc_y = 12, 19, 23, 19
        l_i, r_i = intensity * 0.6, intensity * 1.4
    else:
        lc_x, lc_y, rc_x, rc_y = 10, 18, 22, 18
        l_i, r_i = intensity, intensity

    for y in range(32):
        for x in range(32):
            dl = math.sqrt((x - lc_x)**2 + (y - lc_y)**2)
            dr = math.sqrt((x - rc_x)**2 + (y - rc_y)**2)
            val = max(0, (3200 * l_i) - dl * 280,
                         (3000 * r_i) - dr * 280,
                         (700 - abs(x - 16) * 90) if y < 14 else 0)
            grid[y][x] = hw_scale(val + random.gauss(0, 60))
    return grid

def vary_frame(base, variation=1.0, shift_x=0, shift_y=0):
    result = base * variation + np.random.normal(0, hw_scale(70), base.shape)
    if shift_x: result = np.roll(result, shift_x, axis=1)
    if shift_y: result = np.roll(result, shift_y, axis=0)
    return np.clip(result, 0, HW_MAX).astype(int)

def write_csv(filepath, frames, comment=''):
    with open(filepath, 'w') as f:
        if comment: f.write(f'# {comment}\n')
        f.write(f'# Sensore mat data | scale 0-{HW_MAX} | {len(frames)} frames\n')
        for frame in frames:
            flat = frame.flatten().tolist()
            for i in range(32):
                f.write(','.join(map(str, flat[i*32:(i+1)*32])) + '\n')
    print(f'  Written {len(frames):3d} frames -> {filepath}')

# patient_001: symmetric sitting
print('Generating patient_001 (normal sitting, 60 frames)...')
base = sitting_pattern('none', 1.0)
write_csv(os.path.join(OUTPUT_DIR, 'patient_001_normal.csv'),
    [vary_frame(base, 0.95 + 0.1*math.sin(i*0.3),
                random.randint(-1,1), random.randint(-1,1)) for i in range(60)],
    'Patient 001 - normal symmetric sitting')

# patient_002: gradual left lean
print('Generating patient_002 (left lean, 45 frames)...')
bn = sitting_pattern('none', 1.0); bl = sitting_pattern('left', 1.1)
write_csv(os.path.join(OUTPUT_DIR, 'patient_002_left_lean.csv'),
    [vary_frame(bn*(1-i/44) + bl*(i/44), random.uniform(0.9,1.1)) for i in range(45)],
    'Patient 002 - gradual left lean develops over session')

# patient_003: high pressure episode then repositioning
print('Generating patient_003 (high pressure event, 30 frames)...')
base = sitting_pattern('none', 1.0)
def _intensity(i): return random.uniform(1.4,1.7) if 10<=i<=18 else (random.uniform(0.5,0.8) if i>18 else random.uniform(0.9,1.1))
write_csv(os.path.join(OUTPUT_DIR, 'patient_003_high_pressure.csv'),
    [vary_frame(base, _intensity(i), random.randint(-1,1), random.randint(-1,1)) for i in range(30)],
    'Patient 003 - high pressure frames 10-18 then repositioning')

# Format B sample
print('Generating format_b_sample.csv (Format B - 1024 values/row, 20 frames)...')
base = sitting_pattern('right', 1.05)
with open(os.path.join(OUTPUT_DIR, 'format_b_sample.csv'), 'w') as f:
    f.write(f'# Format B: each row = one 32x32 frame (1024 values, scale 0-{HW_MAX})\n')
    for i in range(20):
        f.write(','.join(map(str, vary_frame(base, random.uniform(0.9,1.2)).flatten().tolist())) + '\n')
print(f'  Written  20 frames -> {os.path.join(OUTPUT_DIR, "format_b_sample.csv")}')

print(f'\nAll files use 0-{HW_MAX} scale (same as de0e9b2c_20251013.csv).')
print('Upload at http://127.0.0.1:8000/upload/ -- normalisation is automatic.')
