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

    flake-compat.url = "github:edolstra/flake-compat";
  };

  outputs = { self, nixpkgs, nixos-raspberrypi, argononed, nixos-images, ... }@inputs: let
    allSystems = nixpkgs.lib.systems.flakeExposed;
    forSystems = systems: f: nixpkgs.lib.genAttrs systems (system: f system);
  in {

    lib = nixos-raspberrypi.lib;

    nixosModules = nixos-raspberrypi.nixosModules // {
      docker = { config, lib, pkgs, ... }: {
        # Enable Docker for running the static web server
        virtualisation.docker.enable = true;

        # Run the arcade static container
        virtualisation.oci-containers = {
          backend = "docker";
          containers.arcade-static = {
            image = "ghcr.io/thomas-more-digital-innovation/arcade-cabinet-static:latest";
            ports = [ "80:80" ];
          };
        };

        # Configure the browser to open the web server in kiosk mode
        # We use a systemd user service for Chromium to make it robust (auto-restart)
        systemd.user.services.chromium-kiosk = {
          description = "Chromium Kiosk Service";
          wantedBy = [ "graphical-session.target" ];
          partOf = [ "graphical-session.target" ];
          script = ''
            # Wait for the static web server to be ready (Docker container)
            while ! ${pkgs.curl}/bin/curl -s -o /dev/null -f http://localhost; do
              ${pkgs.coreutils}/bin/sleep 2
            done

            # Clear any stale locks that might prevent starting after a crash
            # Specifically handles cases where hostname changes (e.g. nixos -> ArcadeKast-UANT)
            rm -f $HOME/.config/chromium/SingletonLock

            exec ${pkgs.ungoogled-chromium}/bin/chromium \
              --no-first-run \
              --no-default-browser-check \
              --kiosk \
              --start-maximized \
              --disable-infobars \
              --password-store=basic \
              --noerrdialogs \
              --disable-session-crashed-bubble \
              "http://localhost"
          '';
          serviceConfig = {
            Restart = "always";
            RestartSec = 3;
            # Ensure we have a valid DISPLAY
            Environment = "DISPLAY=:0";
          };
        };

        # Configure the X session startup
        # We use mkForce to override the default chromium startup in rpi5 configs
        services.xserver.displayManager.sessionCommands = lib.mkForce ''
          ${pkgs.xorg.xset}/bin/xset s off
          ${pkgs.xorg.xset}/bin/xset -dpms
          ${pkgs.xorg.xset}/bin/xset s noblank

          # Hide mouse cursor when inactive
          ${pkgs.unclutter-xfixes}/bin/unclutter --timeout 1 &

          # Trigger the user service (systemd will handle the rest)
          ${pkgs.systemd}/bin/systemctl --user start chromium-kiosk &
        '';

        # Ensure the user 'pi' can interact with docker if needed
        users.users.pi.extraGroups = [ "docker" ];

        # Always pull the latest image on startup if online
        systemd.services.docker-arcade-static = {
          preStart = lib.mkBefore ''
            # Check for internet connectivity (ping 8.8.8.8)
            if ${pkgs.iputils}/bin/ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
              echo "Internet detected, pulling latest arcade image..."
              ${pkgs.docker}/bin/docker pull ghcr.io/thomas-more-digital-innovation/arcade-cabinet-static:latest || true
            else
              echo "No internet connection, skipping image pull."
            fi
          '';
        };
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
          directories = [ "/var/log" "/var/lib/nixos" "/var/lib/systemd/coredump" ];
          files = [
            "/etc/machine-id"
            "/etc/ssh/ssh_host_ed25519_key"
            "/etc/ssh/ssh_host_ed25519_key.pub"
            "/etc/ssh/ssh_host_rsa_key"
            "/etc/ssh/ssh_host_rsa_key.pub"
          ];
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
          extraGroups = [ "wheel" "docker" "input" "video" "plugdev" ];
          hashedPassword = "$6$8HEfeFVwfLMMhpY.$e8ZgUExdBzdyi/zZW2Y10M0XdKAuEZ6anx3TNBJz3SyKDt.p7HuxRFWOf.X4yO/ubZ29I2M.Y0n3MUfgOebNR.";
        };

        users.users.root = {
          hashedPassword = "$6$1S4IKvCOc1FqhMig$ohQsKqzkDuES5DBMgYzzBE3OX53miz0T3MHzmIXlvhIrGxM2rAwHq0OEeJfe5FPB973jott3bC7U3u5E6LmOc.";
        };

        environment.systemPackages = with pkgs; [
          tree
          htop
          btop
          fastfetch
          ungoogled-chromium
          dnsutils
          xorg.xset
          input-remapper
          evtest
          unclutter-xfixes
        ];

        services.input-remapper.enable = true;

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

            # Enable the X11 windowing system.
            services.xserver.enable = true;

            # Enable Openbox (extremely lightweight window manager).
            services.xserver.windowManager.openbox.enable = true;
            services.xserver.displayManager.lightdm.enable = true;

            # Configure auto-login for the 'pi' user.
            services.displayManager.autoLogin.enable = true;
            services.displayManager.autoLogin.user = "pi";


            # Disable screensaver and power management in X11
            services.xserver.serverFlagsSection = ''
              Option "BlankTime" "0"
              Option "StandbyTime" "0"
              Option "SuspendTime" "0"
              Option "OffTime" "0"
            '';
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

            # Enable the X11 windowing system.
            services.xserver.enable = true;

            # Enable Openbox (extremely lightweight window manager).
            services.xserver.windowManager.openbox.enable = true;
            services.xserver.displayManager.lightdm.enable = true;

            # Configure auto-login for the 'pi' user.
            services.displayManager.autoLogin.enable = true;
            services.displayManager.autoLogin.user = "pi";


            # Disable screensaver and power management in X11
            services.xserver.serverFlagsSection = ''
              Option "BlankTime" "0"
              Option "StandbyTime" "0"
              Option "SuspendTime" "0"
              Option "OffTime" "0"
            '';
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

            # Enable the X11 windowing system.
            services.xserver.enable = true;

            # Enable Openbox (extremely lightweight window manager).
            services.xserver.windowManager.openbox.enable = true;
            services.xserver.displayManager.lightdm.enable = true;

            # Configure auto-login for the 'pi' user.
            services.displayManager.autoLogin.enable = true;
            services.displayManager.autoLogin.user = "pi";


            # Disable screensaver and power management in X11
            services.xserver.serverFlagsSection = ''
              Option "BlankTime" "0"
              Option "StandbyTime" "0"
              Option "SuspendTime" "0"
              Option "OffTime" "0"
            '';
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

            # Enable the X11 windowing system.
            services.xserver.enable = true;

            # Enable Openbox (extremely lightweight window manager).
            services.xserver.windowManager.openbox.enable = true;
            services.xserver.displayManager.lightdm.enable = true;

            # Configure auto-login for the 'pi' user.
            services.displayManager.autoLogin.enable = true;
            services.displayManager.autoLogin.user = "pi";


            # Disable screensaver and power management in X11
            services.xserver.serverFlagsSection = ''
              Option "BlankTime" "0"
              Option "StandbyTime" "0"
              Option "SuspendTime" "0"
              Option "OffTime" "0"
            '';
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
