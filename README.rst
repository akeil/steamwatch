##########
steamwatch
##########
Watch prices on Steam store


Installation
############
With pip

    $ pip install steamwatch

After installation, create a cron job to update regularly::

    12 * * * * steamwatch fetch


Usage
#####
Start watching a game

.. code:: shell-session

    $ steamwatch watch 12345

Where "12345" is the ``appid`` for that game.

To stop watching:

.. code:: shell-session

    $ steamwatch unwatch 12345

To view all the apps that are watched:

.. code:: shell-session

    $ steamwatch ls

To view recorded changes for all (selected) watched apps:

.. code:: shell-session

    $ steamwatch report
    $ steamwatch report --games 12345 442211

To see recent changes:

.. code:: shell-session

    $ steamwatch recent


Configuration
#############
steamwatch looks for a config file at
- ``/etc/steamwatch.conf`` (global)
- ``~/.config/steamwatch/steamwatch.conf`` (per user)

You can set the following options,
the example shows the default settings:

.. code:: ini

    [steamwatch]
    # sqlite database with local data
    db_path = ~/.local/share/steamwatch.db

    # country code for which to fetch prices
    country_code = us

    # how many entries per game in `steamwatch report`
    report_limit = 5

    # output format for `steamwatch report` (built in: tree, tab)
    report_format = tab

    # output format for `steamwatch ls` (built in: tree, tab)
    list_format = tree

    # how many entries to show in `steamwatch recent`
    recent_limit = 5

    # output format for `steamwatch recent` (built in: tree, tab)
    recent_format = tree
