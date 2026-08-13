<#
.SYNOPSIS
    Machine health and posture report. Read-only, changes nothing.
.DESCRIPTION
    Answers: is this machine clean, activated, unmanaged, secure, and capable
    of running the toolchain? Designed to run as a background job while
    installs proceed, so it costs no wall-clock time.

    Emits lines in the form STATUS|Label|Value where STATUS is
    OK, WARN, FAIL, or INFO. The caller formats and colors them.

    Checks needing elevation degrade to INFO rather than failing.
#>

$out = [System.Collections.Generic.List[string]]::new()
function Add-Line { param($s,$l,$v) $out.Add("$s|$l|$v") }

# ---------- Identity and hardware ----------
try {
    $os  = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $cs  = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    $cpu = Get-CimInstance Win32_Processor -ErrorAction Stop | Select-Object -First 1

    Add-Line "INFO" "Machine"  "$($cs.Name) ($($cs.Manufacturer) $($cs.Model))"
    Add-Line "INFO" "Windows"  "$($os.Caption) $($os.Version) build $([System.Environment]::OSVersion.Version.Build)"
    Add-Line "INFO" "CPU"      "$($cpu.Name.Trim()) ($($cpu.NumberOfCores)C/$($cpu.NumberOfLogicalProcessors)T)"

    $ramGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
    $ramStatus = if ($ramGB -ge 16) { "OK" } elseif ($ramGB -ge 8) { "WARN" } else { "FAIL" }
    Add-Line $ramStatus "Memory" "$ramGB GB"

    $up = (Get-Date) - $os.LastBootUpTime
    Add-Line "INFO" "Uptime" ("{0}d {1}h {2}m" -f $up.Days, $up.Hours, $up.Minutes)
} catch {
    Add-Line "WARN" "Hardware" "could not query: $($_.Exception.Message)"
}

# ---------- Disk ----------
try {
    $sys = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction Stop
    $freeGB  = [math]::Round($sys.FreeSpace / 1GB, 1)
    $totalGB = [math]::Round($sys.Size / 1GB, 1)
    $pct     = [math]::Round(($sys.FreeSpace / $sys.Size) * 100, 0)

    # Visual Studio alone wants 30-50 GB.
    $diskStatus = if ($freeGB -ge 80) { "OK" } elseif ($freeGB -ge 40) { "WARN" } else { "FAIL" }
    Add-Line $diskStatus "Disk C:" "$freeGB GB free of $totalGB GB ($pct%)"
} catch {
    Add-Line "WARN" "Disk" "could not query"
}

# ---------- Windows activation ----------
try {
    $lic = Get-CimInstance SoftwareLicensingProduct -ErrorAction Stop |
        Where-Object { $_.PartialProductKey -and $_.ApplicationID -eq "55c92734-d682-4d71-983e-d6ec3f16059f" } |
        Select-Object -First 1

    if ($lic) {
        $statusText = switch ($lic.LicenseStatus) {
            0 { "Unlicensed" }
            1 { "Activated" }
            2 { "Out-of-box grace" }
            3 { "Out-of-tolerance grace" }
            4 { "Non-genuine grace" }
            5 { "Notification (not activated)" }
            6 { "Extended grace" }
            default { "Unknown ($($lic.LicenseStatus))" }
        }
        $s = if ($lic.LicenseStatus -eq 1) { "OK" } else { "WARN" }
        Add-Line $s "Activation" "$statusText - $($lic.Name)"
    } else {
        Add-Line "INFO" "Activation" "no license product found"
    }
} catch {
    Add-Line "INFO" "Activation" "could not query"
}

# ---------- Management: MDM, Azure AD, domain ----------
try {
    $dsreg = (dsregcmd /status 2>$null | Out-String)

    $aadJoined  = $dsreg -match "AzureAdJoined\s*:\s*YES"
    $domJoined  = $dsreg -match "DomainJoined\s*:\s*YES"
    $workplace  = $dsreg -match "WorkplaceJoined\s*:\s*YES"
    $mdmUrl     = $dsreg -match "MdmUrl\s*:\s*http"

    $joins = @()
    if ($aadJoined) { $joins += "Entra ID joined" }
    if ($domJoined) { $joins += "AD domain joined" }
    if ($workplace) { $joins += "Workplace joined" }
    if ($joins.Count -eq 0) { $joins += "not joined (personal)" }

    Add-Line "INFO" "Join state" ($joins -join ", ")

    # MDM enrollment.
    # Windows ships built-in enrollment scaffolding with EnrollmentState=1 on
    # every machine. Only GUID-named keys with a real provider, a UPN, and a
    # discovery URL represent an actual enrollment.
    $builtIn = @("Local Authority","Cloud Authority","Deploy Authority","WMI_Bridge_SCCM_Server")
    $enrollments = @()
    $ePath = "HKLM:\SOFTWARE\Microsoft\Enrollments"
    if (Test-Path $ePath) {
        $enrollments = Get-ChildItem $ePath -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.PSChildName -notmatch "^\{?[0-9A-Fa-f]{8}-([0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}\}?$") { return }
            $ep = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
            if (-not $ep) { return }
            if ($ep.EnrollmentState -ne 1) { return }
            if (-not $ep.ProviderID) { return }
            if ($builtIn -contains $ep.ProviderID) { return }
            if (-not ($ep.UPN -or $ep.DiscoveryServiceFullURL)) { return }
            $ep.ProviderID
        } | Where-Object { $_ } | Select-Object -Unique
    }

    if ($enrollments -or $mdmUrl) {
        $who = if ($enrollments) { $enrollments -join ", " } else { "unknown provider" }
        Add-Line "WARN" "MDM" "ENROLLED ($who). Policy may block installs or override settings."
    } else {
        Add-Line "OK" "MDM" "not enrolled, no policy management"
    }
} catch {
    Add-Line "INFO" "Management" "could not query"
}

# ---------- Group Policy presence ----------
try {
    $gpo = @()
    foreach ($p in @(
        "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppX",
        "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender",
        "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Installer",
        "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
    )) {
        if (Test-Path $p) { $gpo += (Split-Path $p -Leaf) }
    }
    if ($gpo.Count -gt 0) {
        Add-Line "INFO" "Group Policy" "policies present: $($gpo -join ", ")"
    } else {
        Add-Line "OK" "Group Policy" "no restrictive policy keys found"
    }
} catch { }

# ---------- Defender ----------
try {
    $mp = Get-MpComputerStatus -ErrorAction Stop
    $rtp = if ($mp.RealTimeProtectionEnabled) { "real-time on" } else { "real-time OFF" }
    $age = $mp.AntivirusSignatureAge
    $s = if ($mp.RealTimeProtectionEnabled -and $age -le 7) { "OK" } else { "WARN" }
    Add-Line $s "Defender" "$rtp, signatures ${age}d old"
} catch {
    Add-Line "INFO" "Defender" "could not query (third-party AV, or blocked)"
}

# ---------- Secure Boot ----------
try {
    $sb = Confirm-SecureBootUEFI -ErrorAction Stop
    Add-Line $(if ($sb) { "OK" } else { "WARN" }) "Secure Boot" $(if ($sb) { "enabled" } else { "disabled" })
} catch {
    Add-Line "INFO" "Secure Boot" "requires elevation, or legacy BIOS"
}

# ---------- TPM ----------
try {
    $tpm = Get-Tpm -ErrorAction Stop
    $s = if ($tpm.TpmPresent -and $tpm.TpmReady) { "OK" } else { "WARN" }
    Add-Line $s "TPM" "present=$($tpm.TpmPresent) ready=$($tpm.TpmReady)"
} catch {
    Add-Line "INFO" "TPM" "requires elevation"
}

# ---------- BitLocker ----------
try {
    $bl = Get-BitLockerVolume -MountPoint "C:" -ErrorAction Stop
    $s = if ($bl.ProtectionStatus -eq "On") { "OK" } else { "WARN" }
    Add-Line $s "BitLocker C:" "$($bl.ProtectionStatus), $($bl.VolumeStatus)"
} catch {
    Add-Line "INFO" "BitLocker" "requires elevation"
}

# ---------- Virtualization, needed by WSL2 and Docker ----------
try {
    $cs2 = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    if ($cs2.HypervisorPresent) {
        Add-Line "OK" "Virtualization" "hypervisor present, WSL2 and Docker supported"
    } else {
        $vfw = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue |
               Select-Object -First 1 -ExpandProperty VirtualizationFirmwareEnabled
        if ($vfw) {
            Add-Line "WARN" "Virtualization" "enabled in firmware but no hypervisor running"
        } else {
            Add-Line "FAIL" "Virtualization" "DISABLED in firmware. WSL2 and Docker will not work."
        }
    }
} catch {
    Add-Line "INFO" "Virtualization" "could not query"
}

# ---------- Pending reboot ----------
try {
    $pending = @()
    if (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending") { $pending += "servicing" }
    if (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired") { $pending += "windows update" }
    $sess = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name PendingFileRenameOperations -ErrorAction SilentlyContinue
    if ($sess.PendingFileRenameOperations) { $pending += "file rename" }

    if ($pending.Count -gt 0) {
        Add-Line "WARN" "Pending reboot" "YES ($($pending -join ", ")). Some installs may not complete until you reboot."
    } else {
        Add-Line "OK" "Pending reboot" "none"
    }
} catch { }

# ---------- Windows Update posture ----------
try {
    $lastInstall = (Get-HotFix -ErrorAction Stop | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn
    if ($lastInstall) {
        $days = [int]((Get-Date) - $lastInstall).TotalDays
        $s = if ($days -le 45) { "OK" } elseif ($days -le 90) { "WARN" } else { "FAIL" }
        Add-Line $s "Last patch" "$($lastInstall.ToString('yyyy-MM-dd')) ($days days ago)"
    }
} catch {
    Add-Line "INFO" "Last patch" "could not query"
}

# ---------- Developer posture ----------
try {
    $dev = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" -Name AllowDevelopmentWithoutDevLicense -ErrorAction SilentlyContinue).AllowDevelopmentWithoutDevLicense
    Add-Line $(if ($dev -eq 1) { "OK" } else { "WARN" }) "Developer Mode" $(if ($dev -eq 1) { "enabled" } else { "disabled" })

    $lp = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled
    Add-Line $(if ($lp -eq 1) { "OK" } else { "WARN" }) "Long paths" $(if ($lp -eq 1) { "enabled" } else { "disabled" })
} catch { }

$out
