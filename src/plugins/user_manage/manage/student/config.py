from utils.auth.config import base_info, more_info, privacy_info

more_info = (more_info | privacy_info).copy()
all_info = (base_info | more_info).copy()
