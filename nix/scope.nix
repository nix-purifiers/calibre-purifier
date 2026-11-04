{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.calibre;
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  readLock = import ./read-lock.nix { inherit (pkgs) lib; };
  environment = scope.callPackage ./environment.nix { };
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildCalibreProject = scope.callPackage ./build-project.nix { };
  sdk = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      native = builtins.listToAttrs (
        map
          (path: {
            name = pkgs.lib.removePrefix (toString ../native + "/") (toString path);
            value = builtins.hashFile "sha256" path;
          })
          (
            builtins.filter (path: pkgs.lib.hasSuffix ".py" (toString path)) (
              pkgs.lib.filesystem.listFilesRecursive ../native
            )
          )
      );
      providers = pkgs.lib.genAttrs [ "scope.nix" "environment.nix" ] (
        name: builtins.hashFile "sha256" (./. + ("/" + name))
      );
    }
  );
})
