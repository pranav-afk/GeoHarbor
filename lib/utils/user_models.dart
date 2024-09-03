class UserModel{
  final String ProfilePic;

  UserModel({
  required this.ProfilePic
  });

  factory UserModel.fromMap(Map<String, dynamic>map){
    return UserModel(ProfilePic: map['ProfilePic'] ?? '');
  }

  Map<String, dynamic> toMap() {
    return{
      "profilePic" : ProfilePic,
    };
  }
}
