#!/bin/bash
################################################################################
# MARBEFES EVA Phase 2 - Deployment Script for laguna.ku.lt
# User: razinka (with write access to /srv/shiny-server/EVA/)
# Public URL: https://laguna.ku.lt/EVA/  (internal shiny-server port 3838 is
#             NOT publicly exposed — only reachable on the server itself)
################################################################################

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVER="laguna.ku.lt"
USERNAME="razinka"
APP_NAME="EVA"
SERVER_PATH="/srv/shiny-server/$APP_NAME"
VENV_PATH="$SERVER_PATH/venv"
# Public URL via the HTTPS reverse proxy. Port 3838 is server-local only, so
# on-server checks use http://localhost:3838/$APP_NAME/ instead.
APP_URL="https://laguna.ku.lt/$APP_NAME/"
LOCAL_DIR="$(pwd)"

# Required files
REQUIRED_FILES=(
    "app.py"
    "requirements.txt"
    "www/marbefes.png"
    "www/iecs.png"
)

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[$1/$2]${NC} $3"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_local_files() {
    print_step "1" "10" "Checking local files..."
    local all_present=true

    for file in "${REQUIRED_FILES[@]}"; do
        if [ -f "$LOCAL_DIR/$file" ]; then
            print_success "$file"
        else
            print_error "$file - MISSING"
            all_present=false
        fi
    done

    if [ "$all_present" = false ]; then
        print_error "Some required files are missing. Please ensure all files are present."
        exit 1
    fi
    echo ""
}

test_ssh_connection() {
    print_step "2" "10" "Testing SSH connection to $SERVER..."

    if ssh -o ConnectTimeout=10 -o BatchMode=yes "$USERNAME@$SERVER" "echo 'SSH connection successful'" 2>/dev/null; then
        print_success "SSH connection established"
    else
        print_error "Cannot connect to $SERVER as $USERNAME"
        print_info "Please ensure:"
        echo "   - Your SSH keys are set up"
        echo "   - You have access to $SERVER"
        echo "   - The server is reachable"
        exit 1
    fi
    echo ""
}

create_remote_directory() {
    print_step "3" "10" "Creating application directory on server..."

    ssh "$USERNAME@$SERVER" bash <<EOF
        mkdir -p $SERVER_PATH
        mkdir -p $SERVER_PATH/www
        echo "Directory created: $SERVER_PATH"
EOF

    if [ $? -eq 0 ]; then
        print_success "Application directory ready"
    else
        print_error "Failed to create directory"
        exit 1
    fi
    echo ""
}

upload_files() {
    print_step "4" "10" "Uploading application files..."

    # Upload all Python module files
    print_info "Uploading Python modules..."
    for pyfile in "$LOCAL_DIR"/*.py; do
        if [ -f "$pyfile" ]; then
            scp -q "$pyfile" "$USERNAME@$SERVER:$SERVER_PATH/"
        fi
    done

    # Upload scripts/ directory contents (app imports scripts.sdm_analyse etc).
    # Previously omitted — caused production to drift behind whenever scripts/
    # was modified without a corresponding top-level .py change. Uploads every
    # .py in scripts/ and ensures the remote scripts/ dir exists first.
    if [ -d "$LOCAL_DIR/scripts" ]; then
        print_info "Uploading scripts/ directory..."
        ssh "$USERNAME@$SERVER" "mkdir -p $SERVER_PATH/scripts"
        for scriptfile in "$LOCAL_DIR/scripts"/*.py; do
            if [ -f "$scriptfile" ]; then
                scp -q "$scriptfile" "$USERNAME@$SERVER:$SERVER_PATH/scripts/"
            fi
        done
        # scripts/__init__.py is required for `import scripts.<module>` to work
        if [ ! -f "$LOCAL_DIR/scripts/__init__.py" ]; then
            print_warning "scripts/__init__.py missing locally — remote import may fail"
        fi
    fi

    print_info "Uploading requirements.txt..."
    scp -q "$LOCAL_DIR/requirements.txt" "$USERNAME@$SERVER:$SERVER_PATH/"

    # Upload www directory
    print_info "Uploading static assets (www/)..."
    scp -q -r "$LOCAL_DIR/www" "$USERNAME@$SERVER:$SERVER_PATH/"

    # Upload data directory (only essential files, skip large caches)
    if [ -d "$LOCAL_DIR/data" ]; then
        print_info "Uploading data directory..."
        ssh "$USERNAME@$SERVER" "mkdir -p $SERVER_PATH/data"
        for datafile in "$LOCAL_DIR/data"/*.gpkg "$LOCAL_DIR/data"/*.geojson "$LOCAL_DIR/data"/*.zip; do
            if [ -f "$datafile" ]; then
                scp -q "$datafile" "$USERNAME@$SERVER:$SERVER_PATH/data/" 2>/dev/null || \
                    print_warning "Skipped $(basename "$datafile") (permission denied or too large)"
            fi
        done
    fi

    # Upload optional files if they exist
    [ -f "$LOCAL_DIR/README.md" ] && scp -q "$LOCAL_DIR/README.md" "$USERNAME@$SERVER:$SERVER_PATH/" 2>/dev/null

    print_success "All files uploaded"
    echo ""
}

setup_virtual_environment() {
    print_step "5" "10" "Python environment..."

    # The runtime is the system-wide micromamba env
    # (/opt/micromamba/envs/shiny); shiny-server does NOT use a per-app
    # ./venv. Building one here cost minutes of pointless pip downloads on
    # every deploy (300 MB+ of wheels), so it is skipped. Dependencies are
    # verified — and auto-vendored if missing — against the *real* runtime
    # env in step 8 (verify_deployment).
    print_info "Runtime = /opt/micromamba/envs/shiny — skipping unused ./venv build."
    print_success "Skipped vestigial venv (not used by shiny-server)"
    echo ""
}

install_dependencies() {
    print_step "6" "10" "Dependencies..."

    # No ./venv to install into — deps are checked against the runtime env
    # (and auto-vendored on ModuleNotFoundError) in step 8. This keeps a new
    # requirements.txt entry from silently passing here while the runtime
    # env still lacks it (the old venv install gave exactly that false pass).
    print_info "Deferred to runtime-env verification in step 8."
    print_success "Dependencies handled against the runtime env"
    echo ""
}

set_permissions() {
    print_step "7" "10" "Setting file permissions..."

    ssh "$USERNAME@$SERVER" bash <<EOF
cd $SERVER_PATH

# Set directory permissions (skip errors on files not owned by razinka)
find . -user $USERNAME -type d -exec chmod 755 {} \; 2>/dev/null
find . -user $USERNAME -type f -exec chmod 644 {} \; 2>/dev/null

# Make venv scripts executable
find venv/bin -type f -exec chmod 755 {} \; 2>/dev/null

echo "Permissions set successfully"
EOF

    if [ $? -eq 0 ]; then
        print_success "Permissions configured"
    else
        print_error "Failed to set permissions"
        exit 1
    fi
    echo ""
}

verify_deployment() {
    print_step "8" "10" "Verifying deployment..."

    # IMPORTANT: Shiny Server on laguna runs apps via the system-wide
    # micromamba env at /opt/micromamba/envs/shiny/bin/python3, NOT the
    # ./venv this script builds in step 5–6. We verify against the
    # runtime env so a successful check actually predicts a successful
    # worker spawn.
    #
    # If a package from requirements.txt is missing from the runtime
    # env, the vendored-install fallback below copies it into the app
    # directory (first on sys.path), which requires no sudo and
    # survives future re-deploys (the script only wipes ./venv/).
    ssh "$USERNAME@$SERVER" bash <<'EOF'
set +e
cd /srv/shiny-server/EVA
RUNTIME_PY=/opt/micromamba/envs/shiny/bin/python3
RUNTIME_PIP=/opt/micromamba/envs/shiny/bin/pip

echo "Checking file structure..."
ls -la | head -20

echo ""
echo "Verifying app import against the runtime env ($RUNTIME_PY)..."
IMPORT_OUTPUT=$("$RUNTIME_PY" -c "import app; print('✓ App module imported successfully')" 2>&1)
IMPORT_RESULT=$?
echo "$IMPORT_OUTPUT"

if [ $IMPORT_RESULT -eq 0 ]; then
    echo "✓ Deployment verification passed"
    exit 0
fi

# Extract a ModuleNotFoundError target if present and try the vendored-install fix.
MISSING=$(echo "$IMPORT_OUTPUT" | grep -oE "No module named '[^']+'" | head -1 | sed "s/No module named '//; s/'//")
if [ -z "$MISSING" ]; then
    echo "✗ Import failed for a reason other than a missing module — manual investigation required"
    exit 1
fi

echo ""
echo "⚠ Missing module in runtime env: $MISSING"
echo "Attempting vendored-install fallback (no sudo required)..."

# The requirements.txt distribution name can differ from the import name
# (python-docx -> docx, Pillow -> PIL, scikit-learn -> sklearn, …). Map
# the common cases; otherwise fall back to identity.
case "$MISSING" in
    docx)    DIST=python-docx ;;
    PIL)     DIST=Pillow ;;
    sklearn) DIST=scikit-learn ;;
    yaml)    DIST=PyYAML ;;
    *)       DIST="$MISSING" ;;
esac

"$RUNTIME_PIP" install --user "$DIST" >/tmp/vendor-install.log 2>&1
if [ $? -ne 0 ]; then
    echo "✗ pip install --user failed; see /tmp/vendor-install.log on $HOSTNAME"
    tail -20 /tmp/vendor-install.log
    exit 1
fi

USER_SITE=$("$RUNTIME_PY" -c 'import site; print(site.USER_SITE)')
if [ -d "$USER_SITE/$MISSING" ]; then
    cp -r "$USER_SITE/$MISSING" /srv/shiny-server/EVA/
    cp -r "$USER_SITE/${DIST//-/_}-"*.dist-info /srv/shiny-server/EVA/ 2>/dev/null
    echo "✓ Vendored $MISSING into /srv/shiny-server/EVA/"
else
    echo "✗ Could not locate $MISSING under $USER_SITE — unusual package layout"
    ls "$USER_SITE" | head -20
    exit 1
fi

# Re-verify
"$RUNTIME_PY" -c "import app; print('✓ App module imported successfully (after vendoring)')" 2>&1
exit $?
EOF

    if [ $? -eq 0 ]; then
        print_success "Deployment verified (runtime env)"
    else
        print_error "Runtime-env verification failed — the app will NOT start until fixed"
        echo ""
        echo "Manual recovery:"
        echo "  ssh -t $USERNAME@$SERVER \"sudo /opt/micromamba/envs/shiny/bin/pip install <pkg>\""
        echo "or check the latest log:"
        echo "  ssh $USERNAME@$SERVER \"cat \\\$(ls -t /var/log/shiny-server/EVA-*.log | head -1)\""
    fi
    echo ""
}

configure_shiny_server() {
    print_step "9" "10" "Configuring Shiny Server for virtual environment..."

    ssh "$USERNAME@$SERVER" bash <<'EOF'
# Check if .Rprofile exists in app directory
if [ ! -f "/srv/shiny-server/EVA/.Rprofile" ]; then
    echo "Creating .Rprofile to specify Python path..."
    cat > /srv/shiny-server/EVA/.Rprofile <<'RPROFILE'
# Use virtual environment Python
Sys.setenv(RETICULATE_PYTHON = "/srv/shiny-server/EVA/venv/bin/python")
RPROFILE
    chmod 644 /srv/shiny-server/EVA/.Rprofile
    echo "✓ .Rprofile created"
else
    echo "✓ .Rprofile already exists"
fi

echo ""
echo "Shiny Server configuration checked"
EOF

    print_success "Shiny Server configuration checked"
    echo ""
}

restart_shiny_server() {
    print_step "10" "10" "Restarting Shiny Server..."

    # Primary, no-sudo reload: touching restart.txt makes shiny-server spawn
    # a fresh worker for this app on the next request. A full `systemctl
    # restart` needs sudo that the deploy user does not have non-interactively,
    # so we attempt it but report its outcome HONESTLY instead of the previous
    # code's unconditional "restarted successfully".
    ssh "$USERNAME@$SERVER" bash <<EOF
set -e
touch "$SERVER_PATH/restart.txt"
echo "✓ Touched restart.txt — shiny-server will reload the app on next request"
if sudo -n systemctl restart shiny-server 2>/dev/null; then
    echo "✓ Full shiny-server restart succeeded (passwordless sudo available)"
else
    echo "ℹ No passwordless sudo — relying on the restart.txt app reload (normal here)"
fi
EOF

    if [ $? -eq 0 ]; then
        print_success "App reload triggered (restart.txt)"
    else
        print_error "Could not trigger reload — restart.txt touch failed"
        print_info "Check logs with: ssh $USERNAME@$SERVER 'sudo journalctl -u shiny-server -n 50'"
        exit 1
    fi
    echo ""
}

display_summary() {
    print_header "✓ DEPLOYMENT COMPLETE"

    echo -e "${GREEN}Application successfully deployed!${NC}"
    echo ""
    echo "📍 Application URL:"
    echo -e "   ${BLUE}$APP_URL${NC}"
    echo ""
    echo "🔍 Testing checklist:"
    echo "   □ Open the URL in your browser"
    echo "   □ Verify logos display correctly"
    echo "   □ Upload a CSV file"
    echo "   □ Check calculations work"
    echo "   □ Test visualizations"
    echo ""
    echo "📋 Useful commands:"
    echo -e "   ${BLUE}# View logs${NC}"
    echo "   ssh $USERNAME@$SERVER 'sudo tail -f /var/log/shiny-server.log'"
    echo ""
    echo -e "   ${BLUE}# Check app status${NC}"
    echo "   ssh $USERNAME@$SERVER 'sudo systemctl status shiny-server'"
    echo ""
    echo -e "   ${BLUE}# Restart server${NC}"
    echo "   ssh $USERNAME@$SERVER 'sudo systemctl restart shiny-server'"
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

show_logs() {
    print_header "📋 Viewing Application Logs"

    echo -e "${YELLOW}Press Ctrl+C to exit log viewer${NC}"
    echo ""
    sleep 2

    ssh "$USERNAME@$SERVER" "sudo tail -f /var/log/shiny-server.log"
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header "MARBEFES EVA Phase 2 - Deployment to laguna.ku.lt"

    echo "Target: $APP_URL"
    echo "User: $USERNAME"
    echo ""

    # Execute deployment steps
    check_local_files
    test_ssh_connection
    create_remote_directory
    upload_files
    setup_virtual_environment
    install_dependencies
    set_permissions
    verify_deployment
    configure_shiny_server
    restart_shiny_server

    # Show summary
    display_summary

    # Ask if user wants to view logs — only when attached to a terminal.
    # Non-interactive runs (CI, piped stdin, `< /dev/null`) would otherwise
    # hit EOF here and, under `set -e`, abort with exit 1 *after* a fully
    # successful deploy — the old "deploy reported failure but actually
    # worked" gotcha.
    if [ -t 0 ]; then
        read -p "Would you like to view the application logs? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            show_logs
        fi
    fi
}

# Parse command line arguments
case "${1:-}" in
    --logs)
        ssh "$USERNAME@$SERVER" "sudo tail -f /var/log/shiny-server.log 2>/dev/null || tail -f /var/log/shiny-server/shiny-server.log 2>/dev/null || echo 'Cannot access logs'"
        ;;
    --status)
        ssh "$USERNAME@$SERVER" "systemctl status shiny-server 2>/dev/null || sudo systemctl status shiny-server"
        ;;
    --restart)
        ssh "$USERNAME@$SERVER" "sudo systemctl restart shiny-server"
        echo "Shiny Server restarted"
        ;;
    --help)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  (none)     Run full deployment"
        echo "  --logs     View application logs"
        echo "  --status   Check Shiny Server status"
        echo "  --restart  Restart Shiny Server"
        echo "  --help     Show this help message"
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac

exit 0
