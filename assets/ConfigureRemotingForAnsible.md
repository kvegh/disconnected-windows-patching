# Ansible WinRM configuration script

`ConfigureRemotingForAnsible.ps1` is an unchanged copy of the upstream Ansible script:

https://github.com/ansible/ansible-documentation/blob/devel/examples/scripts/ConfigureRemotingForAnsible.ps1

It configures WinRM listeners, a self-signed HTTPS certificate, firewall access, and local administrator remote access. Basic authentication is enabled unless `-DisableBasicAuth` is supplied. Review the script before running it in an elevated PowerShell session. Downloading or committing it does not execute it.
