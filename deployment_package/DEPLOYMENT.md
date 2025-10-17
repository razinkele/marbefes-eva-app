# MARBEFES EVA App - Deployment Guide

## Deploying to Shiny Server (Python)

### Directory Structure for Deployment

Your app should be organized as follows on the server:

```
/srv/shiny-server/marbefes-eva/
├── app.py                          # Main application file
├── requirements.txt                # Python dependencies
├── www/                            # Static assets directory
│   ├── marbefes.png               # MARBEFES logo
│   └── iecs.png                   # IECS logo
├── MARBEFES_EVA-Phase2_template.xlsx  # Template file
└── sample_data.csv                # Sample data (optional)
```

### Step 1: Prepare requirements.txt

Ensure your `requirements.txt` includes all dependencies:

```txt
shiny>=0.6.0
pandas>=2.0.0
numpy>=1.24.0
openpyxl>=3.1.0
plotly>=5.17.0
```

**Note**: Plotly is required for interactive visualizations (EV charts, heatmaps, histograms).

### Step 2: Server Configuration

#### For Shiny Server Open Source:

Create a configuration file at `/etc/shiny-server/shiny-server.conf`:

```conf
# Define the user we should use when spawning R Shiny processes
run_as shiny;

# Define a top-level server which will listen on a port
server {
  listen 3838;

  # Define the location available at the base URL
  location /marbefes-eva {
    # Directory containing the Shiny app
    app_dir /srv/shiny-server/marbefes-eva;
    
    # Log directory
    log_dir /var/log/shiny-server;
    
    # Python path (adjust to your environment)
    python /usr/bin/python3;
  }
}
```

#### For shinyapps.io (Posit Cloud):

1. Install rsconnect-python:
```bash
pip install rsconnect-python
```

2. Deploy:
```bash
rsconnect deploy shiny . --name your-app-name --title "MARBEFES EVA Phase 2"
```

#### For Hugging Face Spaces:

1. Create `app.py` (already done)
2. Create `requirements.txt` (already done)
3. Push to Hugging Face Spaces repository

### Step 3: File Upload Considerations

**Important**: For production deployment, consider:

1. **File Size Limits**: 
   - Default upload limit is often 5MB
   - Increase if needed in server config

2. **Temporary Storage**:
   - Uploaded files are stored in memory by default
   - For large files, configure temp directory

3. **User Sessions**:
   - Each user gets isolated session
   - Uploaded data is session-specific

### Step 4: Static Assets

Your current setup with `static_assets=Path(__file__).parent / "www"` is correct.

The `www/` directory will be automatically served, making logos accessible at:
- `http://your-domain:3838/marbefes-eva/marbefes.png`
- `http://your-domain:3838/marbefes-eva/iecs.png`

### Step 5: Environment Variables (Optional)

For sensitive configuration, use environment variables:

```python
import os

# In app.py
UPLOAD_MAX_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", "10485760"))  # 10MB default
```

Set in server:
```bash
export UPLOAD_MAX_SIZE=20971520  # 20MB
```

### Step 6: Testing Before Deployment

1. **Test locally with production-like settings**:
```bash
python -m shiny run app.py --host 0.0.0.0 --port 8000
```

2. **Check file paths are relative**:
   - ✅ `Path(__file__).parent / "www"` (good - relative)
   - ❌ `C:\Users\...` (bad - absolute Windows path)

3. **Verify Excel template is accessible**:
```python
# In your app, ensure template path is relative:
template_path = Path(__file__).parent / "MARBEFES_EVA-Phase2_template.xlsx"
```

### Step 7: Security Considerations

1. **Input Validation**:
   - Already implemented: file type checking (`.csv`)
   - Consider adding file size validation

2. **Data Privacy**:
   - Uploaded data is temporary and session-isolated
   - Consider adding data retention policy

3. **Access Control**:
   - If needed, implement authentication
   - Use reverse proxy (nginx) with basic auth

### Step 8: Performance Optimization

1. **Caching**:
   - Cache Excel template reading
   - Use `@functools.lru_cache` for repeated calculations

2. **Resource Limits**:
```python
# Add to app.py if needed
import resource
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, -1))  # 2GB memory limit
```

### Deployment Checklist

- [ ] All file paths are relative (using `Path(__file__).parent`)
- [ ] `requirements.txt` is complete and tested
- [ ] `www/` directory contains all static assets
- [ ] Excel template is included in deployment
- [ ] App runs without errors locally
- [ ] Static assets load correctly
- [ ] File upload works with test data
- [ ] Download functionality tested
- [ ] Server has Python 3.10+ installed
- [ ] Shiny package version is 0.6.0 or higher

### Quick Deployment Commands

**Option 1: Traditional Server**
```bash
# Upload files
scp -r /path/to/app/* user@server:/srv/shiny-server/marbefes-eva/

# SSH to server
ssh user@server

# Install dependencies
cd /srv/shiny-server/marbefes-eva
pip3 install -r requirements.txt

# Restart Shiny Server
sudo systemctl restart shiny-server
```

**Option 2: Docker Deployment**
```bash
# Create Dockerfile (see below)
docker build -t marbefes-eva .
docker run -p 3838:8000 marbefes-eva
```

### Sample Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY MARBEFES_EVA-Phase2_template.xlsx .
COPY www/ ./www/

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "-m", "shiny", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
```

### Monitoring and Logs

**Check logs**:
```bash
# Shiny Server logs
tail -f /var/log/shiny-server/marbefes-eva-*.log

# Application errors
grep -i error /var/log/shiny-server/*.log
```

### Troubleshooting Common Issues

1. **Images not loading (404)**:
   - Verify `www/` directory exists
   - Check `static_assets` parameter in `App()` constructor
   - Ensure image filenames match exactly (case-sensitive on Linux)

2. **Import errors**:
   - Verify all packages in `requirements.txt`
   - Check Python version compatibility

3. **Permission errors**:
   - Ensure shiny user has read access to all files
   ```bash
   sudo chown -R shiny:shiny /srv/shiny-server/marbefes-eva/
   chmod -R 755 /srv/shiny-server/marbefes-eva/
   ```

4. **Upload failures**:
   - Check disk space
   - Verify temp directory permissions
   - Increase upload size limit in server config

### Production URLs

Once deployed, your app will be accessible at:
- Local server: `http://your-server:3838/marbefes-eva/`
- Shinyapps.io: `https://your-account.shinyapps.io/marbefes-eva/`
- Custom domain: `https://marbefes-eva.your-domain.com/`

### Support and Documentation

- Shiny for Python docs: https://shiny.posit.co/py/
- Deployment guide: https://shiny.posit.co/py/docs/deploy.html
- GitHub issues: For app-specific issues

---

**Need help?** Contact your system administrator or refer to the Shiny deployment documentation.
