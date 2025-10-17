# MARBEFES EVA App - Change Log

## Version 2.0.0 - October 2025

### 🎨 New Features

#### Interactive Visualizations
- **Added Plotly Integration**: Replaced placeholder visualizations with fully interactive charts
  - **EV by Subzone**: Bar chart with color gradient showing ecological values
    - Hover to see exact EV values
    - Color scale indicates value magnitude
    - Interactive zoom and pan
  
  - **Feature Distribution**: Heatmap showing feature presence across subzones
    - Visual representation of feature patterns
    - Color-coded presence indicators
    - Hover for detailed information
  
  - **AQ Scores**: Histogram showing distribution of assessment question scores
    - Statistical overview of AQ values
    - Interactive bin selection
    - Frequency distribution analysis

#### Logo Integration
- **Header Logo**: Added MARBEFES logo to navbar (replacing wave emoji)
- **Sidebar Logos**: Both MARBEFES and IECS logos displayed in sidebar
- **Welcome Banner**: Logos integrated into main welcome section
- **Static File Serving**: Properly configured `www/` directory for logo assets

### 🔧 Technical Improvements

#### Code Quality
- **Fixed Deprecations**: Updated `@session.download()` to `@render.download()`
  - Line 787: Template download function
  - Line 994: Results download function
- **Import Organization**: Added Plotly imports (`plotly.graph_objects`, `plotly.express`)
- **Static Assets**: Configured `static_assets` parameter in App constructor

#### Performance
- **Optimized Rendering**: Charts render dynamically based on data
- **Responsive Design**: Visualizations adapt to data size
- **Efficient Data Handling**: Direct Plotly integration for better performance

### 📦 Dependencies

#### New Requirements
- `plotly>=5.17.0` - For interactive visualizations

#### Updated Requirements
All dependencies remain current:
- `shiny>=0.6.0`
- `pandas>=2.0.0`
- `numpy>=1.24.0`
- `openpyxl>=3.1.0`
- `plotly>=5.17.0` ⭐ NEW

### 📁 File Structure

```
deployment_package/
├── app.py                          # Main application (UPDATED)
├── requirements.txt                # Dependencies (UPDATED with plotly)
├── www/                            # Static assets directory
│   ├── marbefes.png               # MARBEFES logo
│   └── iecs.png                   # IECS logo
├── MARBEFES_EVA-Phase2_template.xlsx
├── sample_data.csv
├── README.md                       # Documentation (UPDATED)
├── DEPLOYMENT.md                   # Deployment guide (UPDATED)
├── CHANGELOG.md                    # This file
├── check_deployment.py             # Verification script
├── DEPLOY_INSTRUCTIONS.txt         # Quick start guide
└── .gitignore                     # Git ignore rules
```

### 🚀 Deployment Notes

#### Installation
When deploying to a new environment, ensure plotly is installed:

```bash
pip install -r requirements.txt
```

Or specifically:
```bash
pip install plotly>=5.17.0
```

#### Verification
Run the deployment check script:
```bash
python check_deployment.py
```

Expected output:
```
✓ app.py (41,733 bytes)
✓ requirements.txt (77 bytes)
✓ www/marbefes.png (343,860 bytes)
✓ www/iecs.png (82,650 bytes)
✓ MARBEFES_EVA-Phase2_template.xlsx (17,334,341 bytes)
✓ All required files present!
```

### 🐛 Bug Fixes

- **Fixed**: Static file serving for logo images
- **Fixed**: Deprecation warnings from Shiny framework
- **Fixed**: Visualization placeholders replaced with actual charts
- **Fixed**: Logo display issues in header and sidebar

### 📝 Documentation Updates

- **README.md**: Updated visualization section with Plotly details
- **DEPLOYMENT.md**: Added plotly dependency notes
- **DEPLOY_INSTRUCTIONS.txt**: Updated with latest deployment steps

### ⚡ Breaking Changes

**None** - All changes are backward compatible. If upgrading from a previous version:

1. Install plotly: `pip install plotly>=5.17.0`
2. Replace old `app.py` with new version
3. Ensure `www/` directory contains logo files
4. Restart the Shiny server

### 🔮 Future Enhancements

Potential improvements for future versions:
- Export visualizations as PNG/SVG
- Additional chart types (scatter plots, box plots)
- Custom color scheme editor
- Animation for temporal data
- 3D visualizations for spatial data

### 👥 Contributors

- MARBEFES Project Team
- IECS (Institute of Environmental and Climate Sciences)

### 📄 License

This application is developed for the MARBEFES project, funded by the European Union's Horizon Europe Research Programme.

---

**For support or questions, please contact the MARBEFES project team.**
