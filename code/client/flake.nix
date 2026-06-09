{
  description = "Flake for RaspberryPi support on NixOS";

  nixConfig = {
    extra-substituters = [
      "https://nixos-raspberrypi.cachix.org"
    ];
    extra-trusted-public-keys = [
      "nixos-raspberrypi.cachix.org-1:4iMO9LXa8BqhU+Rpg6LQKiGa2lsNh/j2oiYLNOQ5sPI="
    ];
    connect-timeout = 5;
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

    nixos-raspberrypi = {
      url = "github:nvmd/nixos-raspberrypi/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    argononed = {
      # url = "git+file:../argononed?shallow=1";
      # url = "git+https://gitlab.com/DarkElvenAngel/argononed.git";
      url = "github:nvmd/argononed";
      flake = false;
    };

    nixos-images = {
      # url = "github:nix-community/nixos-images";
      url = "github:nvmd/nixos-images/sdimage-installer";
      # url = "git+file:../nixos-images?shallow=1";
      inputs.nixos-stable.follows = "nixpkgs";
      inputs.nixos-unstable.follows = "nixpkgs";
    };

    impermanence.url = "github:nix-community/impermanence";

    flake-compat.url = "github:edolstra/flake-compat";
  };

  outputs = { self, nixpkgs, nixos-raspberrypi, argononed, nixos-images, impermanence, ... }@inputs: let
    allSystems = nixpkgs.lib.systems.flakeExposed;
    forSystems = systems: f: nixpkgs.lib.genAttrs systems (system: f system);
  in {

    lib = nixos-raspberrypi.lib;

    nixosModules = nixos-raspberrypi.nixosModules // {
      docker = { config, lib, pkgs, ... }: {
        # Docker is enabled, but we manage the container manually in the kiosk service
        virtualisation.docker.enable = true;

        # Consolidated Kiosk Service: Manages Docker container and starts Chromium via Sway (Wayland)
        # We use Sway instead of Cage because Sway supports native cursor autohiding.
        programs.sway = {
          enable = true;
          package = pkgs.sway;
          extraOptions = [ "--unsupported-gpu" ];
          extraPackages = with pkgs; [ swaybg ]; # Required for background support
        };

        # Custom Sway configuration for Kiosk mode
        environment.etc."sway/config".text = lib.mkForce ''
          # Basic configuration
          set $mod Mod4
          font pango:monospace 8
          
          # Input configuration (Belgian layout)
          input "type:keyboard" {
            xkb_layout be
          }

          # Remap Arcade Tab button to close the focused window
          bindsym Tab kill

          # Disable window decorations
          default_border none
          default_floating_border none
          
          # Autohide cursor after 5 seconds
          seat * hide_cursor 5000
          
          # Force all windows to fullscreen (Kiosk mode)
          for_window [class=".*"] fullscreen enable
          for_window [title=".*"] fullscreen enable
          
          # Start the kiosk session
          exec ${pkgs.writeShellScript "kiosk-session" ''
            # 1. Wait for internet and pull image
            PULLED=false
            for i in {1..30}; do
              if ${pkgs.iputils}/bin/ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1; then
                if ${pkgs.docker}/bin/docker pull ghcr.io/thomas-more-digital-innovation/arcade-cabinet-static:latest; then
                  PULLED=true
                fi
                break
              fi
              ${pkgs.coreutils}/bin/sleep 1
            done

            # 2. Manage Docker
            CONTAINER_RUNNING=$(${pkgs.docker}/bin/docker ps -q -f name=arcade-static)
            if [ "$PULLED" = "true" ] || [ -z "$CONTAINER_RUNNING" ]; then
              ${pkgs.docker}/bin/docker stop arcade-static || true
              ${pkgs.docker}/bin/docker rm arcade-static || true
              ${pkgs.docker}/bin/docker run -d --name arcade-static -p 80:80 ghcr.io/thomas-more-digital-innovation/arcade-cabinet-static:latest
              
              # Clean up old/dangling images to prevent storage from filling up
              ${pkgs.docker}/bin/docker image prune -f
            fi

            # 3. Wait for web server
            while ! ${pkgs.curl}/bin/curl -s -o /dev/null -f http://localhost; do
              ${pkgs.coreutils}/bin/sleep 2
            done

            # 4. Launch Chromium in a loop
            while true; do
              # Clear locks
              rm -f /home/pi/.config/chromium/SingletonLock

              ${pkgs.ungoogled-chromium}/bin/chromium \
                --ozone-platform=wayland \
                --ignore-gpu-blocklist \
                --enable-gpu-rasterization \
                --enable-zero-copy \
                --no-first-run \
                --no-default-browser-check \
                --kiosk \
                --start-maximized \
                --disable-infobars \
                --password-store=basic \
                --noerrdialogs \
                --disable-session-crashed-bubble \
                --disable-cache \
                --disk-cache-size=1 \
                --media-cache-size=1 \
                --app="http://localhost"
              
              ${pkgs.coreutils}/bin/sleep 1
            done
          ''}
        '';

        # Auto-login the 'pi' user on TTY1 to start Sway
        services.getty.autologinUser = "pi";

        # Start Sway on login
        programs.bash.loginShellInit = ''
          if [ "$(tty)" = "/dev/tty1" ]; then
            exec sway
          fi
        '';

        # Ensure the 'pi' user can manage docker and has GPU access
        users.users.pi.extraGroups = [ "docker" "video" "render" "input" ];
      };


      immutable = { config, lib, pkgs, ... }: {
        fileSystems."/" = lib.mkForce {
          device = "none";
          fsType = "tmpfs";
          options = [ "defaults" "size=512M" "mode=755" ];
          neededForBoot = true;
        };
        fileSystems."/mnt-root" = {
          device = "/dev/disk/by-label/NIXOS_SD";
          fsType = "ext4";
          neededForBoot = true;
        };
        fileSystems."/nix" = lib.mkForce {
          device = "/mnt-root/nix";
          options = [ "bind" "noatime" ];
          neededForBoot = true;
        };
        fileSystems."/boot/firmware" = lib.mkDefault {
          device = "/dev/disk/by-label/FIRMWARE";
          fsType = "vfat";
          options = [ "nofail" "noatime" "x-systemd.automount" ];
          neededForBoot = true;
        };
        users.mutableUsers = false;
      };

      persistence = { config, lib, ... }: {
        imports = [ inputs.impermanence.nixosModules.impermanence ];
        environment.persistence."/mnt-root/persist" = {
          hideMounts = true;
          directories = [
            "/var/log"
            "/var/lib/nixos"
            "/var/lib/systemd/coredump"
            "/var/lib/docker"
            "/var/lib/NetworkManager"
            "/var/lib/bluetooth"
          ];
          files = [
            "/etc/machine-id"
            "/etc/ssh/ssh_host_ed25519_key"
            "/etc/ssh/ssh_host_ed25519_key.pub"
            "/etc/ssh/ssh_host_rsa_key"
            "/etc/ssh/ssh_host_rsa_key.pub"
          ];
          users.pi = {
            directories = [
              ".config/chromium"
              ".cache/chromium"
              "Downloads"
            ];
          };
        };
      };
    };

    overlays = nixos-raspberrypi.overlays;

    legacyPackages = nixos-raspberrypi.legacyPackages;

    packages = nixos-raspberrypi.packages;

    nixosConfigurations = let

      # TIP: To create "regular" nixosConfigurations look for
      # `nixosSystem` and `nixosSystemFull` helpers in `lib/`
      mkNixOSRPiInstaller = modules: nixos-raspberrypi.lib.nixosInstaller {
        specialArgs = inputs;
        modules = [
          nixos-images.nixosModules.sdimage-installer
          ({ config, lib, modulesPath, ... }: {
            disabledModules = [
              # disable the sd-image module that nixos-images uses
              (modulesPath + "/installer/sd-card/sd-image-aarch64-installer.nix")
            ];
            # nixos-images sets this with `mkForce`, thus `mkOverride 40`
            image.baseName = let
              cfg = config.boot.loader.raspberry-pi;
            in lib.mkOverride 40 "nixos-installer-rpi${cfg.variant}-${cfg.bootloader}";
          })
        ] ++ modules;
      };

      custom-user-config = ({ config, pkgs, lib, ... }: {
        imports = [ self.nixosModules.docker ];

        system.stateVersion = "25.11";
        networking.hostName = "ArcadeKast-UANT";
        users.mutableUsers = false;

        # Set keyboard layout to Belgian
        i18n.defaultLocale = "en_US.UTF-8";
        console.keyMap = "be-latin1";
        services.xserver.xkb = {
          layout = "be";
        };

        services.openssh = {
          enable = true;
          settings = {
            PermitRootLogin = lib.mkForce "yes";
            PasswordAuthentication = true;
          };
        };

        users.users.pi = {
          isNormalUser = true;
          extraGroups = [ "wheel" "docker" "input" "video" "render" "plugdev" ];
          hashedPassword = "$6$8HEfeFVwfLMMhpY.$e8ZgUExdBzdyi/zZW2Y10M0XdKAuEZ6anx3TNBJz3SyKDt.p7HuxRFWOf.X4yO/ubZ29I2M.Y0n3MUfgOebNR.";
        };

        users.users.root = {
          hashedPassword = "$6$1S4IKvCOc1FqhMig$ohQsKqzkDuES5DBMgYzzBE3OX53miz0T3MHzmIXlvhIrGxM2rAwHq0OEeJfe5FPB973jott3bC7U3u5E6LmOc.";
        };
        hardware.graphics.enable = true;
 
        environment.systemPackages = with pkgs; [
          tree
          htop
          btop
          fastfetch
          ungoogled-chromium
          dnsutils
          xorg.xset
          evtest
          unclutter-xfixes
        ];



        services.udev.extraHwdb = ''
          # Match by name
          evdev:name:Ultimarc I-PAC 2:*
            KEYBOARD_KEY_700e0=enter
        '';

        boot.kernelParams = [ "consoleblank=0" ];

        system.nixos.tags = let
          cfg = config.boot.loader.raspberry-pi;
        in [
          "raspberry-pi-${cfg.variant}"
          cfg.bootloader
          config.boot.kernelPackages.kernel.version
        ];
      });

    in {

      rpi02-installer = mkNixOSRPiInstaller [
        ({ config, pkgs, lib, nixos-raspberrypi, ... }: {
          imports = with nixos-raspberrypi.nixosModules; [
            # Hardware configuration
            raspberry-pi-02.base
            usb-gadget-ethernet
          ];
        })
        custom-user-config
      ];

      rpi3-installer = mkNixOSRPiInstaller [
        ({ config, pkgs, lib, nixos-raspberrypi, ... }: {
          imports = with nixos-raspberrypi.nixosModules; [
            # Hardware configuration
            raspberry-pi-3.base
          ];
        })
        custom-user-config
      ];

      rpi4-installer = mkNixOSRPiInstaller [
        ({ config, pkgs, lib, nixos-raspberrypi, ... }: {
          imports = with nixos-raspberrypi.nixosModules; [
            # Hardware configuration
            raspberry-pi-4.base
          ];
        })
        custom-user-config
      ];

      rpi5-installer = mkNixOSRPiInstaller [
        ({ config, pkgs, lib, nixos-raspberrypi, ... }: {
          imports = with nixos-raspberrypi.nixosModules; [
            # Hardware configuration
            raspberry-pi-5.base
            raspberry-pi-5.page-size-16k
          ];
        })
        custom-user-config
      ];

      rpi5 = nixos-raspberrypi.lib.nixosSystem {
        specialArgs = inputs;
        modules = [
          ({ config, pkgs, lib, nixos-raspberrypi, ... }: {
            imports = [
              nixos-raspberrypi.nixosModules.raspberry-pi-5.base
              nixos-raspberrypi.nixosModules.raspberry-pi-5.page-size-16k
              nixos-raspberrypi.nixosModules.raspberry-pi-5.display-vc4

              # Add the sd-image module to make it a bootable SD image
              nixos-raspberrypi.nixosModules.sd-image
            ];

          })
          custom-user-config
        ];
      };

      rpi5-immutable = nixos-raspberrypi.lib.nixosSystem {
        specialArgs = inputs;
        modules = [
          ({ config, pkgs, lib, nixos-raspberrypi, ... }: {
            imports = [
              nixos-raspberrypi.nixosModules.raspberry-pi-5.base
              nixos-raspberrypi.nixosModules.raspberry-pi-5.page-size-16k
              nixos-raspberrypi.nixosModules.raspberry-pi-5.display-vc4

              # Add the sd-image module to make it a bootable SD image
              nixos-raspberrypi.nixosModules.sd-image
              # Make it immutable/stateless
              self.nixosModules.immutable
              self.nixosModules.persistence
            ];


          })
          custom-user-config
        ];
      };

      rpi4 = nixos-raspberrypi.lib.nixosSystem {
        specialArgs = inputs;
        modules = [
          ({ config, pkgs, lib, nixos-raspberrypi, ... }: {
            imports = [
              nixos-raspberrypi.nixosModules.raspberry-pi-4.base
              nixos-raspberrypi.nixosModules.raspberry-pi-4.display-vc4

              # Add the sd-image module to make it a bootable SD image
              nixos-raspberrypi.nixosModules.sd-image
            ];


          })
          custom-user-config
        ];
      };

      rpi4-immutable = nixos-raspberrypi.lib.nixosSystem {
        specialArgs = inputs;
        modules = [
          ({ config, pkgs, lib, nixos-raspberrypi, ... }: {
            imports = [
              nixos-raspberrypi.nixosModules.raspberry-pi-4.base
              nixos-raspberrypi.nixosModules.raspberry-pi-4.display-vc4

              # Add the sd-image module to make it a bootable SD image
              nixos-raspberrypi.nixosModules.sd-image
              # Make it immutable/stateless
              self.nixosModules.immutable
              self.nixosModules.persistence
            ];


          })
          custom-user-config
        ];
      };

    };

    installerImages = let
      nixos = self.nixosConfigurations;
      mkImage = nixosConfig: nixosConfig.config.system.build.sdImage;
      mkUncompressed = nixosConfig: (nixosConfig.extendModules {
        modules = [ { sdImage.compressImage = false; } ];
      }).config.system.build.sdImage;
    in {
      rpi02 = mkImage nixos.rpi02-installer;
      rpi02-uncompressed = mkUncompressed nixos.rpi02-installer;
      rpi3 = mkImage nixos.rpi3-installer;
      rpi3-uncompressed = mkUncompressed nixos.rpi3-installer;
      rpi4 = mkImage nixos.rpi4-installer;
      rpi4-uncompressed = mkUncompressed nixos.rpi4-installer;
      rpi5 = mkImage nixos.rpi5-installer;
      rpi5-uncompressed = mkUncompressed nixos.rpi5-installer;
    };

    sdImages = let
      nixos = self.nixosConfigurations;
      mkImage = nixosConfig: nixosConfig.config.system.build.sdImage;
      mkUncompressed = nixosConfig: (nixosConfig.extendModules {
        modules = [ { sdImage.compressImage = false; } ];
      }).config.system.build.sdImage;
    in {
      rpi5 = mkImage nixos.rpi5;
      rpi5-uncompressed = mkUncompressed nixos.rpi5;
      rpi5-immutable = mkImage nixos.rpi5-immutable;
      rpi5-immutable-uncompressed = mkUncompressed nixos.rpi5-immutable;
    };

  };
}
