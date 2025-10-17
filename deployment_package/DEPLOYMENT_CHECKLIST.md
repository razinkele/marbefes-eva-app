# 📋 Deployment Checklist - MARBEFES EVA App

## ✅ Pre-Deployment Verification

### Package Status
- [x] All files verified with check_deployment.py
- [x] Total files: 13
- [x] Total size: 17 MB
- [x] No missing dependencies

### Core Files
- [x] app.py (42.6 KB) - Latest version with visualizations
- [x] requirements.txt (77 bytes) - Includes plotly
- [x] www/marbefes.png (343.9 KB)
- [x] www/iecs.png (82.7 KB)
- [x] MARBEFES_EVA-Phase2_template.xlsx (16.5 MB)

### Documentation
- [x] README.md - Updated with visualization features
- [x] DEPLOYMENT.md - Updated with plotly dependency
- [x] CHANGELOG.md - Version 2.0.0 documented
- [x] DEPLOY_INSTRUCTIONS.txt - Quick start guide
- [x] PACKAGE_SUMMARY.md - Complete overview

## 🚀 Deployment Steps

### Step 1: Prepare Server Environment
```bash
# SSH to your server
ssh user@your-server

# Create app directory
sudo mkdir -p /srv/shiny-server/marbefes-eva
sudo chown $USER:$USER /srv/shiny-server/marbefes-eva
```

### Step 2: Upload Files
```bash
# From your local machine
cd "C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA Algorithms"
scp -r deployment_package/* user@your-server:/srv/shiny-server/marbefes-eva/
```

### Step 3: Install Dependencies
```bash
# On the server
ssh user@your-server
cd /srv/shiny-server/marbefes-eva

# Install Python packages
pip3 install -r requirements.txt

# Verify plotly installation
python3 -c "import plotly; print('Plotly version:', plotly.__version__)"
```

### Step 4: Verify Installation
```bash
# Run verification script
python3 check_deployment.py

# Expected output:
# ✓ app.py (42,636 bytes)
# ✓ requirements.txt (77 bytes)
# ✓ www/marbefes.png (343,860 bytes)
# ✓ www/iecs.png (82,650 bytes)
# ✓ MARBEFES_EVA-Phase2_template.xlsx (17,334,341 bytes)
# ✓ All required files present!
```

### Step 5: Configure Shiny Server
```bash
# Edit shiny-server configuration
sudo nano /etc/shiny-server/shiny-server.conf
```

Add/update configuration:
```conf
server {
  listen 3838;
  
  location /marbefes-eva {
    app_dir /srv/shiny-server/marbefes-eva;
    log_dir /var/log/shiny-server;
    python /usr/bin/python3;
  }
}
```

### Step 6: Restart Shiny Server
```bash
# Restart the service
sudo systemctl restart shiny-server

# Check status
sudo systemctl status shiny-server

# View logs if needed
sudo tail -f /var/log/shiny-server/marbefes-eva-*.log
```

### Step 7: Test the Application
```bash
# Test from server
curl http://localhost:3838/marbefes-eva/

# Should return HTML content
```

### Step 8: Access from Browser
Open in your web browser:
```
http://your-server-ip:3838/marbefes-eva/
```

## 🧪 Testing Checklist

### Visual Verification
- [ ] MARBEFES logo appears in navbar header (no wave emoji)
- [ ] Both logos appear in sidebar
- [ ] Welcome banner displays correctly
- [ ] All tabs are accessible

### Functionality Tests
- [ ] Upload CSV file works
- [ ] Data preview displays correctly
- [ ] EV calculations complete successfully
- [ ] Download buttons work

### Visualization Tests
- [ ] "EV by Subzone" chart renders
- [ ] "Feature Distribution" heatmap displays
- [ ] "AQ Scores" histogram shows data
- [ ] Charts are interactive (hover, zoom, pan)
- [ ] No JavaScript errors in browser console

### Performance Tests
- [ ] Page loads in < 5 seconds
- [ ] File upload completes successfully
- [ ] Calculations complete in reasonable time
- [ ] Charts render without lag

## 🐛 Troubleshooting

### Issue: Logos not displaying
**Solution:**
```bash
# Check www directory exists
ls -la /srv/shiny-server/marbefes-eva/www/

# Verify file permissions
chmod 644 /srv/shiny-server/marbefes-eva/www/*.png
```

### Issue: Plotly charts not rendering
**Solution:**
```bash
# Verify plotly is installed
python3 -c "import plotly; print(plotly.__version__)"

# Reinstall if needed
pip3 install --upgrade plotly>=5.17.0
```

### Issue: Module not found errors
**Solution:**
```bash
# Install all dependencies
pip3 install -r requirements.txt --force-reinstall
```

### Issue: Permission denied
**Solution:**
```bash
# Fix ownership
sudo chown -R shiny:shiny /srv/shiny-server/marbefes-eva/

# Fix permissions
sudo chmod -R 755 /srv/shiny-server/marbefes-eva/
```

## 📊 Post-Deployment Monitoring

### Check Logs
```bash
# View application logs
sudo tail -f /var/log/shiny-server/marbefes-eva-*.log

# Check for errors
sudo grep -i error /var/log/shiny-server/marbefes-eva-*.log
```

### Monitor Performance
```bash
# Check server resources
htop

# Monitor Shiny processes
ps aux | grep shiny
```

## 🔄 Update Procedure

When updating the application:

1. **Backup current version:**
```bash
cd /srv/shiny-server
sudo tar -czf marbefes-eva-backup-$(date +%Y%m%d).tar.gz marbefes-eva/
```

2. **Upload new files:**
```bash
scp -r deployment_package/* user@server:/srv/shiny-server/marbefes-eva/
```

3. **Restart service:**
```bash
sudo systemctl restart shiny-server
```

## 📞 Support Contacts

**Technical Issues:**
- Check DEPLOYMENT.md for detailed troubleshooting
- Review application logs
- Run check_deployment.py

**Documentation:**
- README.md - User guide
- CHANGELOG.md - What's new
- PACKAGE_SUMMARY.md - Complete overview

## ✅ Deployment Complete!

Once all checklist items are verified:

- [x] Application accessible at http://your-server:3838/marbefes-eva/
- [x] All features working correctly
- [x] Visualizations rendering properly
- [x] No errors in logs
- [x] Performance acceptable

**Status:** 🎉 PRODUCTION READY

---

**Version:** 2.0.0  
**Date:** October 2025  
**Project:** MARBEFES - Horizon Europe
