# Git-based deployment script for Need Mo Matcha Bot
# Usage: .\deploy.ps1

# Configuration
$PiIP = "192.168.1.167"  # Your Pi's IP address
$PiUser = "pi"            # Your Pi's username

Write-Host "Deploying via Git..." -ForegroundColor Green
Write-Host "You'll be prompted for your Pi password" -ForegroundColor Yellow

# Push to GitHub first
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git add .
git commit -m "Deploy update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push origin main

# Pull and restart on Pi
Write-Host "Updating Pi..." -ForegroundColor Yellow
$sshResult = ssh ${PiUser}@${PiIP} @"
cd ~/NeedMoMatchaBot
git pull origin main
pip install -r requirements.txt
sudo systemctl restart matcha-bot
echo 'Git deployment complete!'
"@

# Check if the SSH command was successful
if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment complete!" -ForegroundColor Green
    Write-Host "Check bot status: ssh ${PiUser}@${PiIP} 'sudo systemctl status matcha-bot'" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Deployment failed!" -ForegroundColor Red
    Write-Host "SSH output: $sshResult" -ForegroundColor Yellow
    Write-Host "Please check the Pi connection and try again." -ForegroundColor Yellow
    exit 1
} 