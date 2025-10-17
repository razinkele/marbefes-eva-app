# Quick Start Guide - MARBEFES EVA Phase 2 App

## 🚀 Get Started in 3 Steps

### Step 1: Start the Application

Open a terminal and run:

```bash
cd "c:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA Algorithms"
python -m shiny run app.py --port 8000
```

The app will be available at: **http://127.0.0.1:8000**

### Step 2: Load Sample Data

1. Open the app in your browser
2. Navigate to **Data Input** tab
3. Fill in the form:
   - **EC Name**: "Benthic Habitats"
   - **Study Area**: "Test Area"
   - **Data Type**: Select "qualitative"
   - **Description**: "Sample benthic habitat data"
4. Click **Upload CSV Data File** and select `sample_data.csv`

### Step 3: Explore Results

1. Go to **EC Features** to see feature statistics
2. Check **AQ + EV Results** for calculated values
3. View **Total EV** for summary statistics
4. Download results using the download button

## 📊 Understanding the Output

### Ecological Value (EV)
- Represents the ecological importance of each subzone
- Calculated based on feature presence/absence
- Range: 0 (lowest) to 1 (highest)

### Assessment Questions (AQ)
- Series of questions that evaluate different ecological aspects
- Combined to produce the final EV score

### Total EV
- Aggregates EV across all subzones
- Provides summary statistics (Total, Average, Max, Min)

## 🎯 Tips

- **Use the template**: Download the CSV template from the Data Input tab
- **Check data format**: Ensure first column is "Subzone ID"
- **Multiple datasets**: Run separate assessments for different ECs
- **Download results**: Save your results as CSV for further analysis

## 📁 Files Included

- `app.py` - Main Shiny application
- `README.md` - Detailed documentation
- `requirements.txt` - Python dependencies
- `sample_data.csv` - Example dataset
- `analyze_excel.py` - Excel analysis script

## 🔧 Stopping the App

Press `CTRL+C` in the terminal where the app is running.

## ❓ Need Help?

Refer to `README.md` for detailed documentation and troubleshooting.

---

**Project**: MARBEFES - Horizon Europe
**Version**: Phase 2
**Created**: Based on template by A. Franco (15/10/2025)
