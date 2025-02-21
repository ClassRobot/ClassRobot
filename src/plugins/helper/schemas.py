from utils.helper import Helper, Helpers


class HelperMenu:
    def __init__(self, *helpers: Helper):
        self.helpers: Helpers = Helpers()
        self.extend(*helpers)

    def to_string(self):
        return "\n".join(helper.overview() for helper in self.helpers)

    def extend(self, *helpers: Helper):
        self.helpers.extend(helpers)

    def get_helper(self, command: str) -> Helper | None:
        return self.helpers.get_helper(command)


helper_menu = HelperMenu()
