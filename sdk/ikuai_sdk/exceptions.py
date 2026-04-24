class IKuaiError(Exception):
    pass


class IKuaiValidationError(IKuaiError):
    pass


class IKuaiNetworkError(IKuaiError):
    pass
