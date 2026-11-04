{
  lib,
  runCommand,
  writeText,
  fetchurl,
  fetchgit,
  python3,
  original,
  purifier,
  sdk,
}:
{
  lock,
  fetchers ? { },
}:
let
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/calibre_purifier_install_request.py
      ../native/calibre_purifier_native.py
    ];
  };
  checked = purifier.checkLock lock;
  nativeFetch =
    args:
    fetchurl (
      args
      // {
        curlOptsList = [
          "--cacert"
          "${original}/share/calibre/calibre-ebook-root-CA.crt"
        ];
      }
    );
  tree = purifier.tree (
    {
      name = "calibre-plugin-archives";
      entries = checked.entries;
      inherit
        runCommand
        writeText
        fetchgit
        python3
        ;
      fetchurl = nativeFetch;
    }
    // fetchers
  );
  context = writeText "calibre-lock.json" (builtins.toJSON checked.data);
  request = writeText "calibre-native-install.json" (
    builtins.toJSON {
      action = "install";
      catalog = checked.data.native.catalog;
      entries = map (entry: {
        inherit (entry) path calibre;
        archive = "${tree}/${entry.path}";
      }) checked.entries;
    }
  );
in
assert lib.assertMsg (checked.data.sdk == sdk) "calibre SDK changed; update the purifier lock";
runCommand "calibre-locked-environment" { passthru = { inherit tree; }; } ''
  export HOME="$TMPDIR/home" XDG_CONFIG_HOME="$TMPDIR/config" XDG_DATA_HOME="$TMPDIR/data" XDG_CACHE_HOME="$TMPDIR/cache" QT_QPA_PLATFORM=offscreen
  export CALIBRE_CONFIG_DIRECTORY="$TMPDIR/calibre" PYTHONNOUSERSITE=1
  export CALIBRE_PURIFIER_REQUEST="$TMPDIR/request.json" CALIBRE_PURIFIER_RESPONSE="$TMPDIR/response.json"
  mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$CALIBRE_CONFIG_DIRECTORY" "$out"
  ${python3}/bin/python ${driver}/calibre_purifier_install_request.py ${request} "$out" "$CALIBRE_PURIFIER_REQUEST"
  ${original}/bin/calibre-debug --exec-file ${driver}/calibre_purifier_native.py > "$TMPDIR/native.log"
  test -f "$out/manifest.json"
  ln -s ${context} "$out/lock.json"
''
