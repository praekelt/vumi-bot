from twisted.internet.defer import inlineCallbacks, returnValue

from zope.interface import implements

from vumi.tests.helpers import (
    MessageHelper, WorkerHelper, MessageDispatchHelper, PersistenceHelper,
    generate_proxies, IHelper,
)

from vumibot.base import BotWorker


class BotMessageProcessorHelper(object):
    """
    Test helper for message processors.

    This helper construct and wraps several lower-level helpers and provides
    higher-level functionality for app worker tests.

    :param message_processor_class:
        The worker class for the application being tested.

    :param \**msg_helper_args:
        All other keyword params are passed to the underlying
        :class:`~vumi.tests.helpers.MessageHelper`.
    """

    implements(IHelper)

    def __init__(self, message_processor_class, **msg_helper_args):
        self.message_processor_class = message_processor_class
        self.persistence_helper = PersistenceHelper(use_riak=False)
        self.msg_helper = MessageHelper(**msg_helper_args)
        self.transport_name = self.msg_helper.transport_name
        self.worker_helper = WorkerHelper(self.msg_helper.transport_name)
        self.dispatch_helper = MessageDispatchHelper(
            self.msg_helper, self.worker_helper)

        # Proxy methods from our helpers.
        generate_proxies(self, self.msg_helper)
        generate_proxies(self, self.worker_helper)
        generate_proxies(self, self.dispatch_helper)
        generate_proxies(self, self.persistence_helper)

    def setup(self):
        self.persistence_helper.setup()
        self.worker_helper.setup()

    @inlineCallbacks
    def cleanup(self):
        yield self.worker_helper.cleanup()
        yield self.persistence_helper.cleanup()

    @inlineCallbacks
    def get_message_processor(self, config):
        """
        Get an instance of a worker class.

        :param config: Config dict.
        :param cls: The Application class to instantiate.
                    Defaults to :attr:`application_class`
        :param start: True to start the application (default), False otherwise.

        Some default config values are helpfully provided in the
        interests of reducing boilerplate:

        * ``transport_name`` defaults to :attr:`self.transport_name`
        """
        cls = self.message_processor_class
        cls_name = '.'.join((cls.__module__, cls.__name__))
        app_config = self.mk_config({
            'message_processors': {cls_name: self.mk_config(config)},
        })
        app_config.setdefault('transport_name', self.msg_helper.transport_name)
        app = yield self.get_worker(BotWorker, app_config)
        [proc] = app.message_processors
        returnValue(proc)
