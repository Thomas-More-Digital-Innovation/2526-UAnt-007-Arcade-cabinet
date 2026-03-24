{ config, lib, pkgs, ... }:

{
  # An "immutable" System Implementation (Stateless / Erase Your Darlings)
  #
  # This configuration mounts a tmpfs (in-memory filesystem) on the root (/).
  # Any changes made to the system during a session (in /etc, /var, /home, etc.)
  # will be wiped clean upon every reboot.
  #
  # The actual Nix store (/nix) remains on the SD card to avoid using too much RAM.

  # Use tmpfs for the root filesystem
  fileSystems."/" = lib.mkForce {
    device = "none";
    fsType = "tmpfs";
    # Size 2G is usually plenty for a RPi, adjust if needed.
    # It only stores files created at runtime that aren't in /nix.
    options = [ "defaults" "size=512M" "mode=755" ];
    neededForBoot = true;
  };

  # Mount the physical SD card partition (labeled NIXOS_SD) at a temporary location
  fileSystems."/mnt-root" = {
    device = "/dev/disk/by-label/NIXOS_SD";
    fsType = "ext4";
    neededForBoot = true;
  };

  # Bind-mount the /nix from the SD card to the runtime /nix
  fileSystems."/nix" = lib.mkForce {
    device = "/mnt-root/nix";
    options = [ "bind" "noatime" ];
    neededForBoot = true;
  };

  # Keep the firmware partition at /boot/firmware
  # This is where the RPi bootloader, config.txt, and kernels live.
  fileSystems."/boot/firmware" = lib.mkDefault {
    device = "/dev/disk/by-label/FIRMWARE";
    fsType = "vfat";
    options = [ "nofail" "noatime" "x-systemd.automount" ];
  };

  # Disable local user changes 
  users.mutableUsers = false;

  # TIP: If you want to persist specific data (like SSH host keys or logs),
  # you would typically use the 'impermanence' module or manual bind-mounts 
  # to a persistent partition.
}
