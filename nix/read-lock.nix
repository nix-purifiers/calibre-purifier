{ lib }:
{
  src,
  lockFile ? src + "/calibre-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  component = s: builtins.isString s && builtins.match "[A-Za-z0-9][A-Za-z0-9_.+-]*" s != null;
  selection =
    if builtins.pathExists (src + "/calibre-purifier.json") then
      builtins.fromJSON (builtins.readFile (src + "/calibre-purifier.json"))
    else
      null;
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "calibre"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.selection or null)
    && data.selection == selection
    && builtins.isList (data.selection.plugins or null)
    && builtins.all (name: builtins.isString name && name != "") data.selection.plugins
    && builtins.isAttrs (data.native.catalog or null)
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && component (e.path or null)
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://" e.url
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isAttrs (e.calibre or null)
      && builtins.isString (e.calibre.name or null)
      && builtins.isString (e.calibre.index_name or null)
      && builtins.isList (e.calibre.version or null)
      && e.calibre.version != [ ]
      && builtins.all builtins.isInt e.calibre.version
      && builtins.isAttrs (data.native.catalog.${e.path} or null)
    ) entries
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.length entries == builtins.length data.selection.plugins
    && builtins.length (lib.unique (map (e: e.calibre.name) entries)) == builtins.length entries
    &&
      builtins.sort builtins.lessThan (map (e: e.calibre.index_name) entries)
      == builtins.sort builtins.lessThan data.selection.plugins;
in
{
  purifier = "calibre";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "calibre lock is missing, malformed, or stale; run calibre-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
