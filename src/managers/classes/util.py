from utils.models.enums import JoinMethod

join_method_dict = {
    "申请加入": JoinMethod.apply,
    "邀请加入": JoinMethod.invite,
    "直接通过": JoinMethod.direct,
}
