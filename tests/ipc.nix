{
  pkgs,
  scope,
  hostNetns,
}:
let
  hooks = pkgs.lib.fileset.toSource {
    root = ../native/hooks;
    fileset = pkgs.lib.fileset.fileFilter (file: file.hasExt "py") ../native/hooks;
  };
  profile = scope.environment {
    lock = scope.readLock { src = ../examples/minimal; };
  };
in
pkgs.runCommand "calibre-native-ipc-isolation"
  {
    CALIBRE_PROOF_HOST_NETNS = hostNetns;
    CALIBRE_PROOF_DEBUG = "${pkgs.calibre}/bin/calibre-debug";
    CALIBRE_PROOF_HOLDER = ./ipc_holder.py;
    CALIBRE_PROOF_CHECK = ./ipc_check.py;
    CALIBRE_PROOF_HOOKS = hooks;
  }
  ''
    export HOME="$TMPDIR/home" XDG_CONFIG_HOME="$TMPDIR/config" XDG_DATA_HOME="$TMPDIR/data" XDG_CACHE_HOME="$TMPDIR/cache" QT_QPA_PLATFORM=offscreen
    export CALIBRE_CONFIG_DIRECTORY="$TMPDIR/calibre" CALIBRE_PURIFIER_ENVIRONMENT=${profile}
    mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$CALIBRE_CONFIG_DIRECTORY" "$out"
    ${pkgs.calibre}/bin/calibre-debug --exec-file ${./ipc_test.py} > "$out/proof.txt"
  ''
