############
Entry Points
############

TODO
Explain python entry points,
link to python docs

All entry points are used in the ``setup.py`` file of the ``steamwatch``
package. Thus, this can be used as an example.

The following entry points are defined:

- ``steamwatch.signals``
    - ``app_added = <callable>``
    - ``app_removed = <callable>``
    - ``package_linked = <callable>``
    - ``threshold = <callable>``
    - ``currency_changed = <callable>``
    - ``price_changed = <callable>``
    - ``release_date_changed = <callable>``
    - ``coming_soon_changed = <callable>``
    - ``supports_linux_changed = <callable>``


Signals
#######
All of the ``steamwatch.signals`` entry points expect a *callable* as a
parameter. The callable must look like this:

.. py:function:: handler(signal_name, application, **kwargs)

    Steamwatch signal handler.

    :param str signal_name:
        The name of the emitted signal.
        This matches the name of the signal for which you have registered
        the handler and can be useful if the same handler is registered for
        multiple signals.
    :param object application:
        a Reference to the :class:`steamwatch.application.Application`
        instance that emitted the signal.
    :param dict kwargs:
        Passed *kwargs* depend on the kind of signal being emitted

        ``app_added``,
        ``app_removed``
            ``app=app`` - Reference to the :class:`steamwatch.model.App` that
            was added or removed.

        ``package_linked``
            ``package=pkg, app=app`` - The affected
            :class:`steamwatch.model.Package`
            and :class:`steamwatch.model.App`.

        ``currency_changed``,
        ``price_changed``,
        ``release_date_changed``,
        ``coming_soon_changed``,
        ``supports_linux_changed``,
            ``current=current,  previous=previous,  package=package`` - The
            current and previous value of the field that changed
            and a reference to the affected :class:`steamwatch.model.Package`.
