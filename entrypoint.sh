#!/usr/bin/env bash

#shellcheck disable=SC2086
exec \
    /usr/bin/python3 \
        /app/plex_media_reanalyzer.py \
            --config /app/config \
            "$@"