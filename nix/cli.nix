{
  lib,
  runCommand,
  writeText,
  makeWrapper,
  python3,
  original,
  sdk,
  nix,
  gh,
  cacert,
  nixpkgsSrc,
  purifierSrc,
}:
let
  integration = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      (lib.fileset.fileFilter (file: file.hasExt "py") ../calibre_purifier)
      (lib.fileset.fileFilter (file: file.hasExt "py") ../native)
      (lib.fileset.fileFilter (file: file.hasExt "nix") ./.)
    ];
  };
  bootstrap = writeText "calibre-purifier-main.py" "import os,runpy,sys; sys.path.insert(0, ${builtins.toJSON integration}); sys.argv[0]=os.environ['CALIBRE_PURIFIER_COMMAND']; runpy.run_module('calibre_purifier.main',run_name='__main__')";
  realize = writeText "calibre-purifier-realize.nix" ''
    { lockPath, projectPath, target ? "environment" }:
    let
      pkgs = import (builtins.storePath "${nixpkgsSrc}") {};
      scope = import ${integration}/nix/scope.nix {
        inherit pkgs;
        nixpkgsSrc = builtins.storePath "${nixpkgsSrc}";
        purifierSrc = builtins.storePath "${purifierSrc}";
      };
      lockFile = builtins.toPath lockPath;
      src = if target == "environment" then builtins.toPath projectPath else builtins.path {
        path = builtins.toPath projectPath;
        name = "calibre-project";
        filter = path: type: !(builtins.elem (baseNameOf path) [ ".git" ".calibre-purifier" "__pycache__" "result" ]);
      };
      build = scope.buildCalibreProject { inherit src lockFile; };
    in if target == "environment" then scope.environment { lock = scope.readLock { inherit src lockFile; }; }
       else if target == "project" then build.packages.project
       else if target == "release" then build.release
       else throw "Unknown CALIBRE purifier target"
  '';
in
runCommand "calibre-purifier" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin"
  for name in calibre-purifier calibre calibre-complete calibre-customize calibre-debug calibre-parallel calibre-server calibre-smtp calibredb ebook-convert ebook-device ebook-edit ebook-meta ebook-polish ebook-viewer fetch-ebook-metadata lrf2lrs lrfviewer lrs2lrf markdown-calibre web2disk; do
    makeWrapper ${python3}/bin/python "$out/bin/$name" \
      --add-flags ${bootstrap} \
      --set CALIBRE_PURIFIER_COMMAND "$name" \
      --set CALIBRE_PURIFIER_NATIVE ${integration}/native \
      --set CALIBRE_PURIFIER_ORIGINAL ${original} \
      --set CALIBRE_PURIFIER_HOOKS ${integration}/native/hooks \
      --set CALIBRE_PURIFIER_SDK ${sdk} \
      --set CALIBRE_PURIFIER_REALIZE ${realize} \
      --set-default CALIBRE_PURIFIER_GH ${gh}/bin/gh \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default NIX_SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --prefix PATH : ${
        lib.makeBinPath [
          nix
          gh
        ]
      }
  done
''
