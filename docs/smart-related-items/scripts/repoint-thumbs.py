#!/usr/bin/env python3
"""For each demo clip, set the main poster thumbnail to a freshly-transcoded one
(so the player stops showing the old funda/hacks/mumsnet/elgiganten footer).

Drops every thumbnail whose id < the cutoff (anything before the recent re-upload).
Marks the new _15.jpg variant as main.
"""
import json, sys, subprocess

# Cutoff: all IDs <= this are "old" (from the original upload).
# New thumbnails created after the re-upload start at 1778594...
CUTOFF = 1778594000000000

CLIPS = ["7281312","7281315","7281317","7281318","7281319","7281320",
         "7281321","7281322","7281323","7281324","7281325","7281327"]

def get_clip(cid):
    p = subprocess.run(
        ["curl","-sS",f"https://demo.bbvms.com/json/mediaclip/{cid}"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(p.stdout)

def pick_main(thumbs):
    """Return the id of the new _15.jpg thumbnail, or None."""
    new = [t for t in thumbs if int(t.get("id","0")) >= CUTOFF]
    if not new:
        return None
    # Prefer a frame at 15s (steady mid-intro frame), else the first new one.
    for t in new:
        if "_15.jpg" in t.get("src",""):
            return t["id"]
    return new[0]["id"]

def build_update(clip):
    thumbs = clip.get("thumbnails") or []
    new_main_id = pick_main(thumbs)
    if not new_main_id:
        return None
    # Keep ONLY thumbnails created in the recent re-upload (id >= CUTOFF).
    new_thumbs = []
    for t in thumbs:
        if int(t.get("id","0")) < CUTOFF:
            continue
        # Strip legacy top-level "main" — only the crops.<set>.main field matters now.
        is_main = (t["id"] == new_main_id)
        crops = t.get("crops") or {"landscape": {"x":0,"y":0,"width":1,"height":1}}
        for setname in crops:
            crops[setname]["main"] = is_main
        new_thumbs.append({
            "id":     t["id"],
            "src":    t["src"],
            "width":  t.get("width","1280"),
            "height": t.get("height","720"),
            "main":   False,
            "crops":  crops,
        })
    return {"thumbnails": new_thumbs, "_picked_main": new_main_id, "_n_thumbs": len(new_thumbs)}

if __name__ == "__main__":
    for cid in CLIPS:
        clip = get_clip(cid)
        upd = build_update(clip)
        if not upd:
            print(f"{cid}  ✗ no new thumbnails found — skipping")
            continue
        print(f"{cid}  main->{upd['_picked_main']} (of {upd['_n_thumbs']} new thumbs)")
        # Write the patch to /tmp so we can hand it to sapi_put_from_file
        payload = {"thumbnails": upd["thumbnails"]}
        with open(f"/tmp/thumb-patch-{cid}.json","w") as f:
            json.dump(payload, f, indent=2)
