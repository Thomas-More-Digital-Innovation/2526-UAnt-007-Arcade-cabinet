BUILD (Regular SD):  `nix build .#sdImages.rpi5 --print-build-logs`
BUILD (Immutable): `nix build .#sdImages.rpi5-immutable --print-build-logs`

FLASH: `zstdcat result/sd-image/*.img.zst | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync`
DECOMPRESS: `zstd -d result/sd-image/nixos* -o rpi5-nixos.img`
CALIGULA: `sudo caligula burn result/sd-image/nixos*`

UPDATE:
`nixos-rebuild switch --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false`
UPDATE with sshpass:
`sshpass -p "nixos" nixos-rebuild switch --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false`

UPDATE (boot):
`sshpass -p "nixos" nixos-rebuild boot --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false`

GENERATE Password for hashedPassword:
`mkpasswd -m sha-512`
