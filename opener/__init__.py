# Copyright (C) 2021 taylor.fish <contact@taylor.fish>
#
# This file is part of Opener.
#
# Opener is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Opener is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Opener. If not, see <https://www.gnu.org/licenses/>.

# flake8: noqa

# Wrapper that calls `.transformations.transform`. We avoid importing
# `.transformations` directly since it would negatively impact startup time,
# even if we just need to display the help message.
def transform(*args, **kwargs):
    from .transformations import transform
    return transform(*args, **kwargs)  # Currently returns `None`
