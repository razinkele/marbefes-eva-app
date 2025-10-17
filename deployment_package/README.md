# MARBEFES EVA Phase 2 - Python Shiny Application

## Overview

This is a Python Shiny web application that implements Phase 2 of the Ecological Value Assessment (EVA) framework for the MARBEFES project. The application provides an interactive interface for calculating ecological values based on ecosystem component data.

## Features

The application includes the following sections:

### 1. **Home**
- Welcome page with project information
- Overview of the EVA framework
- Getting started guide

### 2. **Acronyms**
- Reference table for all acronyms used in the assessment
- Includes EVA, EV, EC, AQ, and feature-specific acronyms

### 3. **Data Input**
- Upload gridded data for ecosystem components
- Configure EC name, study area, and data type
- CSV file upload functionality
- Template download option
- Data preview and validation

### 4. **EC Features**
- Configure ecosystem component features
- View feature summaries and statistics
- Analyze feature distributions

### 5. **AQ + EV Results**
- View calculated Assessment Question (AQ) scores
- Display Ecological Value (EV) for each subzone
- Detailed results table

### 6. **Total EV**
- Aggregate ecological values across all components
- Summary statistics (Total, Average, Max, Min EV)
- Downloadable results
- Detailed EV breakdown by subzone

### 7. **Visualization**
- Interactive Plotly charts and plots
- Multiple visualization types:
  - **EV by Subzone**: Bar chart with color gradient showing ecological values
  - **Feature Distribution**: Heatmap showing feature presence across subzones
  - **AQ Scores**: Histogram showing distribution of assessment scores
- Customizable color schemes
- Hover interactions, zoom, and pan capabilities

## Installation

### Prerequisites
- Python 3.13+ (or compatible version)
- Conda environment (recommended)

### Required Packages

The following packages are required:
```
shiny
pandas
openpyxl
numpy
plotly
```

### Setup Instructions

1. **Install dependencies:**
   ```bash
   pip install shiny pandas openpyxl numpy plotly
   ```

   Or if using conda:
   ```bash
   conda install shiny pandas openpyxl numpy plotly
   ```

2. **Verify installation:**
   ```bash
   python -c "import shiny; print(shiny.__version__)"
   ```

## Running the Application

### Option 1: Using Shiny CLI (Recommended)

```bash
shiny run app.py
```

The app will start and be available at `http://127.0.0.1:8000`

### Option 2: Using Python Directly

```bash
python -m shiny run app.py
```

### Option 3: Specify Port and Host

```bash
shiny run app.py --port 8080 --host 0.0.0.0
```

## Usage Guide

### Step 1: Prepare Your Data

Your data should be in CSV format with the following structure:

```csv
Subzone ID,Feature1,Feature2,Feature3,...
A0,1,0,1,...
A1,0,1,0,...
A2,1,1,0,...
...
```

- **First column**: Subzone IDs (grid cells)
- **Subsequent columns**: Features (species or habitats)
- **Values**: Presence/absence (0/1) or quantitative data

### Step 2: Upload Data

1. Navigate to the **Data Input** tab
2. Fill in the metadata:
   - EC Name
   - Study Area
   - Data Type (qualitative or quantitative)
   - Description
3. Click "Upload CSV Data File" and select your file
4. Preview your data to ensure it loaded correctly

### Step 3: Configure Features

1. Go to the **EC Features** tab
2. Review detected features and their characteristics
3. View summary statistics

### Step 4: View Results

1. Navigate to **AQ + EV Results** to see:
   - Assessment Question scores
   - Calculated Ecological Values for each subzone

2. Go to **Total EV** to see:
   - Aggregated statistics
   - Total ecological value across all subzones
   - Download results as CSV

### Step 5: Visualize Data

1. Open the **Visualization** tab
2. Select visualization type
3. Choose color scheme
4. Explore your data visually

## Data Template

Download a template CSV file directly from the app:
1. Go to **Data Input** tab
2. Click "Download CSV Template"
3. Fill in your data
4. Upload the completed file

## Project Information

**Template created by:** A. Franco on 15/10/2025

**Reference:** Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA)

**Funding:** MARBEFES project has received funding from the European Union's Horizon Europe research and innovation programme.

## Notes

### Current Implementation

This is a functional prototype that demonstrates the core workflow. The current version includes:

- ✅ Full UI structure matching the Excel template
- ✅ Data upload and preview
- ✅ Basic EV calculations
- ✅ Results download
- ✅ Summary statistics
- ⚠️ Simplified AQ calculations (full 9-question assessment to be implemented)
- ⚠️ Visualization placeholders (interactive charts to be added)

### Future Enhancements

The following features could be added in future versions:

1. **Complete AQ Calculations:**
   - AQ1-AQ9 detailed implementation
   - Feature rarity classification
   - Ecological significance scoring

2. **Advanced Visualizations:**
   - Interactive plotly charts
   - Spatial maps
   - Heatmaps
   - Time-series analysis

3. **Multiple EC Support:**
   - Upload multiple ecosystem components
   - Cross-EC comparisons
   - Integrated total EV across all ECs

4. **Data Validation:**
   - Input validation
   - Error handling
   - Data quality checks

5. **Export Options:**
   - Export to Excel
   - PDF reports
   - Interactive dashboards

## Troubleshooting

### App won't start
- Ensure all dependencies are installed
- Check Python version compatibility
- Verify no other app is using port 8000

### File upload issues
- Ensure file is in CSV format
- Check file encoding (UTF-8 recommended)
- Verify first column contains Subzone IDs

### Calculation errors
- Verify data contains numeric values
- Check for missing or NaN values
- Ensure proper column headers

## Support

For questions or issues related to the EVA framework, please refer to:
- Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA)

## License

This application is part of the MARBEFES project, funded by the European Union's Horizon Europe programme.
