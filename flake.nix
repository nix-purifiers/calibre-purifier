{
  description = "calibre with locked, Nix-resolved add-ons";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        calibre-purifier = import ./nix/scope.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (
        system:
        let
          p = (pkgsFor system).calibre-purifier;
        in
        {
          default = p.cli;
          calibre = p.original;
          xvfb = (pkgsFor system).xvfb-run;
          gui-test-env =
            let
              pkgs = pkgsFor system;
            in
            pkgs.runCommand "purifier-gui-test-environment" { } ''
              mkdir -p "$out/bin"
              ln -s ${pkgs.lib.getBin pkgs.dbus}/bin/dbus-run-session "$out/bin/dbus-run-session"
              ln -s ${pkgs.lib.getBin pkgs.dbus}/bin/dbus-daemon "$out/bin/dbus-daemon"
              ln -s ${
                pkgs.makeFontsConf {
                  fontDirectories = [
                    pkgs.dejavu_fonts
                    pkgs.noto-fonts
                  ];
                }
              } "$out/fonts.conf"
            '';
        }
      );
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/calibre-purifier";
        };
      });
      lib.calibre-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      lib.calibre-purifier.checkProcessIsolation =
        { system, hostNetns }:
        let
          pkgs = pkgsFor system;
        in
        import ./tests/ipc.nix {
          inherit pkgs hostNetns;
          scope = pkgs.calibre-purifier;
        };

      checks = forAll (
        system:
        let
          p = (pkgsFor system).calibre-purifier;
          build = p.buildCalibreProject { src = ./examples/minimal; };
        in
        {
          cli = p.cli;
          inherit (build.packages) environment project;
          release = build.release;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
