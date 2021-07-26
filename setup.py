# Copyright (c) 2021 Joshua Thomas, Lambdanaut. All rights reserved.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

from setuptools import setup

setup(name='voicemsg',
      version='0.1',
      description='Library to record audio until a silence is encountered',
      url='http://github.com/lambdanaut/voicemsg',
      author='Lambdanaut',
      author_email='lambdanaut@protonmail.com',
      license='GNU General Public License v3 or later (GPLv3+)',
      packages=['voicemsg'],
      zip_safe=False)
