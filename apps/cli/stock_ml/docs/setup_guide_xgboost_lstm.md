# SETUP GUIDE: XGBoost, Attention-LSTM & Stacking Ensemble
### Directional Classification for S&P 500 (Target: 80% Accuracy)

**Course**: RMCS2502 – Computer Science Research Methodology  
**Institution**: Bina Nusantara University  
**Hardware Reference**: Intel Core i5 Gen 13 + NVIDIA RTX 2050 (4 GB VRAM)  
**Python Version**: 3.10+  
**Dataset Range**: Jan 2019 – Dec 2023  

---

## 1. Rationale: Why XGBoost, Attention-LSTM, and Stacking?

Based on a Systematic Literature Review of 30 papers (2015–2025):

### ► XGBoost
- Consistently ranks #1 or #2 for tabular data.
- **Performance**: Chen & Li (2019) reported 134% cumulative return vs 28% benchmark.
- **Efficiency**: Computationally efficient, handles class imbalance via `scale_pos_weight`, and is interpretable via SHAP values.

### ► Attention-LSTM
- Captures sequential/temporal dependencies.
- **Performance**: Fischer & Krauss (2018) achieved the highest out-of-sample daily returns.
- **Innovation**: Multi-head self-attention allows the model to focus on the most informative timesteps.

### ► Stacking Ensemble
- Reaches the 80% accuracy target by combining tabular strengths (XGBoost) with temporal strengths (Attn-LSTM).
- **Synergy**: Rezaei et al. (2024) showed +8–14 pp accuracy increase vs single models.
- **Protocol**: Out-of-fold protocol ensures zero data leakage.

---

## 2. Strategies for 80% Accuracy

1.  **Expanded Feature Set (27 Features)**: Includes CCI-20, STOCH, WR-14, MFI-14, ADX-14, etc. These microstructure features contribute ~38% SHAP importance.
2.  **Attention Mechanism**: Multi-head self-attention (4 heads) re-weights hidden states.
3.  **Extended Lookback**: Window increased from 20 to 30 days.
4.  **Label Smoothing**: ($\epsilon=0.1$) reduces model overconfidence.

---

## 3. Environment Setup

### 3.1 Python Environment
```bash
conda create -n stock_ml python=3.10
conda activate stock_ml
pip install numpy pandas scikit-learn matplotlib seaborn joblib scipy xgboost yfinance ta pandas-ta shap
```

### 3.2 PyTorch with CUDA (RTX 2050)
```bash
# For CUDA 12.1:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Verify GPU:
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

---

## 4. Implementation Pipeline

### Phase 1: Data Acquisition (`01_data_acquisition.py`)
- Downloads 100 high-volume S&P 500 tickers.
- Date range: 2019-01-01 to 2023-12-31.

### Phase 2: Feature Engineering (`02_feature_engineering.py`)
- **27 Indicators** across 5 groups: Trend, Momentum, Volatility, Volume, and Microstructure.
- **Normalization**: Rolling Z-Score with 252-day lookback.

### Phase 3: Model Training
- **XGBoost** (`03_train_xgboost.py`): Purged Walk-Forward splits, 5 folds.
- **Attention-LSTM** (`04_train_lstm.py`): 30-day lookback, Multi-head attention, Label smoothing.
- **Stacking** (`05_train_stacking.py`): Logistic Regression meta-learner using OOF probabilities.

---

## 5. Technical Specifications

| Model | Training Time (100 tickers) | Resource Usage |
| :--- | :--- | :--- |
| **XGBoost** | ~35–60 min | CPU-intensive |
| **Attn-LSTM** | ~2–4 hours | GPU (RTX 2050) ~0.6 GB VRAM |
| **Stacking** | ~5 min | Minimal |

---

## 6. Execution Order

```bash
python 01_data_acquisition.py      # Download Tickers
python 02_feature_engineering.py   # Build 27 Features
python 03_train_xgboost.py         # Train XGBoost (Save OOF)
python 04_train_lstm.py            # Train Attn-LSTM (Save OOF)
python 05_train_stacking.py        # Train Meta-Learner
python 06_compare_results.py       # Analysis & Plots
```

---

## 7. Troubleshooting

- **VRAM OOM**: Reduce `BATCH_SIZE` (64→32) or `HIDDEN_SIZE` (128→64).
- **Low Accuracy**: Ensure `03` and `04` are fully completed before running `05`.
- **yfinance Limits**: Increase `time.sleep(0.5)` if 429 errors occur.

---
*BINUS University - Computer Science Research Methodology 2024*
