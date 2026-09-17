import subprocess

def check_netstat():
    print("Checking netstat for port 8000...")
    try:
        res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        lines = [line for line in res.stdout.splitlines() if ":8000" in line]
        print("Netstat lines for 8000:")
        for line in lines:
            print("  ", line)
    except Exception as e:
        print("Error netstat:", e)

def check_firewall():
    print("\nChecking Windows Firewall for Schemora or 8000...")
    try:
        cmd = "Get-NetFirewallRule -DisplayName '*Schemora*' | Select-Only Name, DisplayName, Enabled, Direction, Action"
        res = subprocess.run(["powershell", "-Command", "Get-NetFirewallRule | Where-Object {$_.DisplayName -like '*Schemora*' -or $_.DisplayName -like '*8000*'} | Format-Table Name, DisplayName, Enabled, Action"], capture_output=True, text=True)
        print(res.stdout)
    except Exception as e:
        print("Error firewall:", e)

if __name__ == "__main__":
    check_netstat()
    check_firewall()
