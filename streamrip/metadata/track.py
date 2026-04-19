from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .album import AlbumMetadata
from .util import safe_get, typed

logger = logging.getLogger("streamrip")


def _tidal_quality_from_resp(resp: dict) -> int:
    quality_map: dict[str, int] = {
        "LOW": 0,
        "HIGH": 1,
        "LOSSLESS": 2,
        "HI_RES": 3,
    }

    tidal_quality = typed(resp.get("audioQuality", "LOW"), str)
    quality = quality_map.get(tidal_quality, 0)
    tags = safe_get(resp, "mediaMetadata", "tags", default=[])
    if isinstance(tags, list) and "HIRES_LOSSLESS" in tags:
        quality = max(quality, 3)

    return quality


def _format_replaygain(v) -> str | None:
    if v is None:
        return None
    try:
        return f"{float(v):+.2f} dB"
    except (TypeError, ValueError):
        return str(v)


def _first_not_none(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def _merge_names(base_names: str | None, role_names: list[str] | None) -> str | None:
    merged: list[str] = []
    if base_names:
        merged.extend(name.strip() for name in base_names.split(",") if name.strip())
    if role_names:
        for name in role_names:
            if name not in merged:
                merged.append(name)
    if not merged:
        return None
    return ", ".join(merged)


@dataclass(slots=True)
class TrackInfo:
    id: str
    quality: int

    bit_depth: Optional[int] = None
    explicit: bool = False
    sampling_rate: Optional[int | float] = None
    work: Optional[str] = None


@dataclass(slots=True)
class TrackMetadata:
    info: TrackInfo

    title: str
    album: AlbumMetadata
    artist: str
    tracknumber: int
    discnumber: int
    composer: str | None
    artists: list[str] | None = None
    author: str | None = None
    compilation: int = 0
    isrc: str | None = None
    lyrics: str | None = ""
    replaygain_track_gain: str | None = None
    source_platform: str | None = None
    source_track_id: str | None = None
    source_album_id: str | None = None
    source_artist_id: str | None = None

    @classmethod
    def from_qobuz(cls, album: AlbumMetadata, resp: dict) -> TrackMetadata | None:
        title = typed(resp["title"].strip(), str)
        isrc = typed(resp["isrc"], str)
        streamable = typed(resp.get("streamable", False), bool)

        if not streamable:
            return None

        version = typed(resp.get("version"), str | None)
        work = typed(resp.get("work"), str | None)
        if version is not None and version not in title:
            title = f"{title} ({version})"
        if work is not None and work not in title:
            title = f"{work}: {title}"

        base_composer = typed(resp.get("composer", {}).get("name"), str | None)
        parsed_roles = typed(resp.get("_parsed_performer_roles"), dict | None)
        role_composers = []
        role_authors = []
        if isinstance(parsed_roles, dict):
            role_composers = typed(parsed_roles.get("Composer"), list | None) or []
            role_authors = (typed(parsed_roles.get("Author"), list | None) or []) + (
                typed(parsed_roles.get("Lyricist"), list | None) or []
            )
        composer = _merge_names(base_composer, role_composers)
        author = _merge_names(None, role_authors)
        tracknumber = typed(resp.get("track_number", 1), int)
        discnumber = typed(resp.get("media_number", 1), int)
        artist = typed(
            safe_get(
                resp,
                "performer",
                "name",
            ),
            str,
        )
        artists: list[str] = [artist]
        track_id = str(resp["id"])
        source_album_id = typed(safe_get(resp, "album", "id"), int | str | None)
        source_artist_id = typed(safe_get(resp, "performer", "id"), int | str | None)
        bit_depth = typed(resp.get("maximum_bit_depth"), int | None)
        sampling_rate = typed(resp.get("maximum_sampling_rate"), int | float | None)
        replaygain_track_gain = _format_replaygain(
            _first_not_none(
                safe_get(resp, "audio_info", "replaygain_track_gain"),
                resp.get("replaygain_track_gain"),
                resp.get("gain"),
            )
        )
        # Is the info included?
        explicit = False

        info = TrackInfo(
            id=track_id,
            quality=album.info.quality,
            bit_depth=bit_depth,
            explicit=explicit,
            sampling_rate=sampling_rate,
            work=work,
        )
        return cls(
            info=info,
            title=title,
            album=album,
            artist=artist,
            tracknumber=tracknumber,
            discnumber=discnumber,
            composer=composer,
            artists=artists,
            author=author,
            isrc=isrc,
            replaygain_track_gain=replaygain_track_gain,
            source_platform="qobuz",
            source_track_id=track_id,
            source_album_id=str(source_album_id)
            if source_album_id is not None
            else None,
            source_artist_id=str(source_artist_id)
            if source_artist_id is not None
            else None,
        )

    @classmethod
    def from_deezer(cls, album: AlbumMetadata, resp) -> TrackMetadata | None:
        track_id = str(resp["id"])
        isrc = typed(resp["isrc"], str)
        bit_depth = 16
        sampling_rate = 44.1
        explicit = typed(resp["explicit_lyrics"], bool)
        work = None
        title = typed(resp["title"], str)
        artist = typed(resp["artist"]["name"], str)
        artists = [
            typed(a["name"], str)
            for a in typed(resp.get("contributors"), list | None) or []
        ]
        if not artists:
            artists = [artist]
        tracknumber = typed(resp["track_position"], int)
        discnumber = typed(resp["disk_number"], int)
        composer = None
        source_album_id = typed(safe_get(resp, "album", "id"), int | str | None)
        source_artist_id = typed(safe_get(resp, "artist", "id"), int | str | None)
        info = TrackInfo(
            id=track_id,
            quality=album.info.quality,
            bit_depth=bit_depth,
            explicit=explicit,
            sampling_rate=sampling_rate,
            work=work,
        )
        return cls(
            info=info,
            title=title,
            album=album,
            artist=artist,
            tracknumber=tracknumber,
            discnumber=discnumber,
            composer=composer,
            artists=artists,
            isrc=isrc,
            source_platform="deezer",
            source_track_id=track_id,
            source_album_id=str(source_album_id)
            if source_album_id is not None
            else None,
            source_artist_id=str(source_artist_id)
            if source_artist_id is not None
            else None,
        )

    @classmethod
    def from_soundcloud(cls, album: AlbumMetadata, resp: dict) -> TrackMetadata:
        track = resp
        track_id = track["id"]
        isrc = typed(safe_get(track, "publisher_metadata", "isrc"), str | None)
        bit_depth, sampling_rate = None, None
        explicit = typed(
            safe_get(track, "publisher_metadata", "explicit", default=False),
            bool,
        )

        title = typed(track["title"].strip(), str)
        artist = typed(track["user"]["username"], str)
        artists = [artist]
        tracknumber = 1

        info = TrackInfo(
            id=track_id,
            quality=album.info.quality,
            bit_depth=bit_depth,
            explicit=explicit,
            sampling_rate=sampling_rate,
            work=None,
        )
        return cls(
            info=info,
            title=title,
            album=album,
            artist=artist,
            tracknumber=tracknumber,
            discnumber=0,
            composer=None,
            artists=artists,
            isrc=isrc,
            source_platform="soundcloud",
            source_track_id=str(track_id),
            source_album_id=str(album.info.id),
            source_artist_id=str(track.get("user", {}).get("id"))
            if track.get("user", {}).get("id") is not None
            else None,
        )

    @classmethod
    def from_tidal(cls, album: AlbumMetadata, track) -> TrackMetadata:
        title = typed(track["title"], str).strip()
        item_id = str(track["id"])
        isrc = typed(track["isrc"], str)
        version = track.get("version")
        explicit = track.get("explicit", False)
        if version:
            title = f"{title} ({version})"

        tracknumber = typed(track.get("trackNumber", 1), int)
        discnumber = typed(track.get("volumeNumber", 1), int)

        artists = typed(track.get("artists"), list | None) or []
        if len(artists) > 0:
            artist_names = [typed(a.get("name"), str) for a in artists]
            artist = ", ".join(artist_names)
            source_artist_id = typed(artists[0].get("id"), int | str | None)
        else:
            artist = track["artist"]["name"]
            artist_names = [artist]
            source_artist_id = typed(safe_get(track, "artist", "id"), int | str | None)

        source_album_id = typed(safe_get(track, "album", "id"), int | str | None)

        lyrics = track.get("lyrics", "")
        replaygain_track_gain = _format_replaygain(
            _first_not_none(track.get("replayGain"), track.get("gain"))
        )

        quality = _tidal_quality_from_resp(track)
        sampling_rate = typed(
            track.get("maximumSamplingRate") or track.get("maximum_sampling_rate"),
            int | float | None,
        )
        bit_depth = typed(
            track.get("maximumBitDepth") or track.get("maximum_bit_depth"),
            int | None,
        )

        if quality >= 2:
            if sampling_rate is None:
                sampling_rate = 44100
            if bit_depth is None:
                if quality == 3:
                    bit_depth = 24
                else:
                    bit_depth = 16
        else:
            sampling_rate = bit_depth = None

        info = TrackInfo(
            id=item_id,
            quality=quality,
            bit_depth=bit_depth,
            explicit=explicit,
            sampling_rate=sampling_rate,
            work=None,
        )
        return cls(
            info=info,
            title=title,
            album=album,
            artist=artist,
            tracknumber=tracknumber,
            discnumber=discnumber,
            composer=None,
            artists=artist_names,
            isrc=isrc,
            lyrics=lyrics,
            replaygain_track_gain=replaygain_track_gain,
            source_platform="tidal",
            source_track_id=item_id,
            source_album_id=str(source_album_id)
            if source_album_id is not None
            else None,
            source_artist_id=str(source_artist_id)
            if source_artist_id is not None
            else None,
        )

    @classmethod
    def from_resp(cls, album: AlbumMetadata, source, resp) -> TrackMetadata | None:
        if source == "qobuz":
            return cls.from_qobuz(album, resp)
        if source == "tidal":
            return cls.from_tidal(album, resp)
        if source == "soundcloud":
            return cls.from_soundcloud(album, resp)
        if source == "deezer":
            return cls.from_deezer(album, resp)
        raise Exception

    def format_track_path(self, format_string: str) -> str:
        # Available keys: "tracknumber", "artist", "albumartist", "composer", "title",
        # and "explicit", "albumcomposer"
        none_text = "Unknown"
        info = {
            "id": self.info.id,
            "title": self.title,
            "tracknumber": self.tracknumber,
            "artist": self.artist,
            "artists": ", ".join(self.artists or [self.artist]),
            "albumartist": self.album.albumartist,
            "albumcomposer": self.album.albumcomposer or none_text,
            "composer": self.composer or none_text,
            "explicit": " (Explicit) " if self.info.explicit else "",
            "source_platform": self.source_platform or none_text,
        }
        return format_string.format(**info)
