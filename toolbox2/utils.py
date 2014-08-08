import logging
import toolbox2


def is_option_available(tool, option, regex=False):
    """Return True if the specified option is available in the specified tool

    The implementation is as simple as parsing the help output of the tool.

    :param tool: the tool to check
    :type tool: string

    :param option: the option we are looking for
    :type option: string

    :param regex: if True, consider option as a regex
    :type regex: bool

    :return is_option_available
    :rtype bool
    """
    logger = logging.getLogger('toolbox2')

    loader = toolbox2.Loader()
    Action = loader.get_class('getcapability')
    action = Action(logger,
                    '/tmp/',
                    None,
                    {'tool': tool, 'option': option, 'regex': regex},
                    {})
    success = action.run()
    if success:
        logger.info('Tool %s does support option %s', tool, option)
    else:
        logger.info('Tool %s does not support option %s', tool, option)
    return success
