# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Basic Openenv Environment.

The basic_openenv environment is a simple test environment that echoes back messages.
"""

from pydantic import Field

from openenv.core.env_server.types import Action, Observation


class BasicOpenenvAction(Action):
    """Action for the Basic Openenv environment - just a message to echo."""

    message: str = Field(..., description="Message to echo back")


class BasicOpenenvObservation(Observation):
    """Observation from the Basic Openenv environment - the echoed message."""

    echoed_message: str = Field(default="", description="The echoed message")
    message_length: int = Field(default=0, description="Length of the echoed message")
