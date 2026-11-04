{
  lib,
  runCommand,
  python3,
  original,
  environment,
  readLock,
  gnutar,
  gzip,
}:
{
  src,
  lockFile ? src + "/calibre-purifier.lock.json",
  script ? "build.py",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
}:
let
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/calibre_purifier_run_build.py
      ../native/calibre_purifier_prepare.py
    ];
  };
  lock = readLock { inherit src lockFile; };
  profile = environment { inherit lock fetchers; };
  hooks = lib.fileset.toSource {
    root = ../native/hooks;
    fileset = lib.fileset.fileFilter (file: file.hasExt "py") ../native/hooks;
  };
  projectSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".calibre-purifier"
        "__pycache__"
        "result"
      ]);
  };
  project = runCommand "calibre-project" { } ''
    export CALIBRE_PURIFIER_ENVIRONMENT=${profile} CALIBRE_PURIFIER_COMMAND_BINARY=${original}/bin/calibre-debug
    export CALIBRE_PURIFIER_HOOKS=${hooks}
    export CALIBRE_PYTHON_PATH=${original}/lib/calibre CALIBRE_RESOURCES_PATH=${original}/share/calibre
    export CALIBRE_EXTENSIONS_PATH=${original}/lib/calibre/calibre/plugins CALIBRE_EXECUTABLES_PATH=${original}/bin
    export CALIBRE_PURIFIER_OUTPUT="$out"
    mkdir -p "$out"
    cp -r ${projectSource} project
    chmod -R u+w project
    cd project
    export CALIBRE_PURIFIER_SCRIPT="$PWD/"${lib.escapeShellArg script}
    ${python3}/bin/python ${driver}/calibre_purifier_run_build.py
    ${lib.optionalString doCheck checkCommand}
  '';
  release =
    runCommand "calibre-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -cf - -C ${project} . | gzip -n > "$out/calibre-project.tar.gz"
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = profile;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
