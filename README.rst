.. _Steam store: http://store.steampowered.com/
.. _SteamDB: https://steamdb.info


##########
steamwatch
##########
This is a small command line app to the development of prices
and other properties on the `Steam store`_.

It is inspired by (but not related to) SteamDB_.

You install *steamwatch* locally and run it periodically
to collect data on selected games available on steam. 
The app uses an undocumented API that is also used by
the Steam desktop client.
No account required, all data is stored locally.


Installation
############
With pip

    $ pip install steamwatch

After installation, you will probably want to
create a cron job to update regularly::

    12 * * * * steamwatch fetch

Of course, any other way to periodically execute ``steamwatch fetch``
will work.


Usage
#####
Start watching a game

.. code:: shell-session

    $ steamwatch watch 12345

Where "12345" is the ``appid`` for that game.
You can find the ``appid`` for a game through its URL on the store page::

    http://store.steampowered.com/app/316750/
                                      ^^^^^^
                                      appid

To stop watching a game:

.. code:: shell-session

    $ steamwatch unwatch 12345

To view all the games that you are watching:

.. code:: shell-session

    $ steamwatch ls

To view recorded changes for all (or some) watched games:

.. code:: shell-session

    $ steamwatch report
    $ steamwatch report --games 12345 442211

To see recent changes across all watched titles:

.. code:: shell-session

    $ steamwatch recent


Configuration
#############
Configuration files are:

global:
    ``/etc/steamwatch.conf``
user:
    ``~/.config/steamwatch/steamwatch.conf``

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


Steam Store Structure
#####################
Steam structures its store into *Apps* and *Packages*.
An *App* is what you would usually understand to be the "game",
e.g. "Civilization V".
A *Package* is what you actually buy when you purchase a game.
Every title will have some kind of default package that includes
just the game. Other packages may include additional content
or special editions of the game.

Each package has its own price and this, *Packages* are the entities
that are tracked with *steamwatch*.

When you ``watch`` a game, all of it's packages are added to
the watchlist and the ``ls``, ``report`` and ``recent``
commands all list packages (sometimes grouped by game).
