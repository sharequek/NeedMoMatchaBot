# One-time service setup script
# Usage: .\setup-service.ps1

# Configuration
$PiIP = "192.168.1.167"  # Your Pi's IP address
$PiUser = "pi"            # Your Pi's username

Write-Host "Setting up service on Pi..." -ForegroundColor Green
Write-Host "You'll be prompted for your Pi password" -ForegroundColor Yellow

$sshResult = ssh ${PiUser}@${PiIP} "cd ~/NeedMoMatchaBot && sudo cp matcha-bot.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable matcha-bot && sudo systemctl start matcha-bot && echo 'SUCCESS: Service setup complete!'"

if ($sshResult -like "*SUCCESS: Service setup complete!*") {
    Write-Host "Service setup complete!" -ForegroundColor Green
    Write-Host "Check bot status: ssh ${PiUser}@${PiIP} 'sudo systemctl status matcha-bot'" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Service setup failed!" -ForegroundColor Red
    Write-Host "SSH output: $sshResult" -ForegroundColor Yellow
    exit 1
} 