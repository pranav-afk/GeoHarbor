import 'package:flutter/material.dart';
import '../pages/login_page.dart';
import '/pages/settings.dart';
//import 'package:flutter_application_1/utils/user_models.dart';
import 'dart:io';
import '/utils/utils.dart';

class NavDrawer extends StatefulWidget {
  const NavDrawer({super.key});

  @override
  State<NavDrawer> createState() => _NavDrawerState();
}

class _NavDrawerState extends State<NavDrawer> {
  File? image;

  void selectImage() async {
    image = await pickImage(context);
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: Container(
        color: Color.fromRGBO(57, 57, 57, 1),
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            UserAccountsDrawerHeader(
              currentAccountPictureSize: Size.square(87),
              accountName: const Text(''), // username
              accountEmail: const Text(''), //user phone number
              currentAccountPicture: SizedBox(
                height: 10,
                child: Align(
                  alignment: Alignment.center,
                  child: Container(
                    child: InkWell(
                        onTap: () => selectImage(),
                        child: image == null
                            ? const CircleAvatar(
                                backgroundColor:
                                    Color.fromARGB(255, 14, 13, 13),
                                maxRadius: 100,
                                child: Icon(
                                  Icons.account_circle,
                                  size: 87,
                                  color: Colors.white,
                                ),
                              )
                            : CircleAvatar(
                                backgroundImage: FileImage(image!),
                                radius: 100,
                              )),
                  ),
                ),
              ),
              decoration: BoxDecoration(
                  color: Color.fromRGBO(57, 57, 57, 1),
                  image: DecorationImage(
                      image: AssetImage('images/bhuvan_header.jpg'),
                      fit: BoxFit.cover)),
            ),
            ListTile(
              leading: Icon(
                Icons.account_circle,
                color: Colors.white,
              ),
              title: Text(
                'Profile',
                style: TextStyle(color: Colors.white),
              ),
              onTap: () => print('stats tapped'),
            ),
            ListTile(
                leading: Icon(
                  Icons.settings,
                  color: Colors.white,
                ),
                title: Text(
                  'Settings',
                  style: TextStyle(color: Colors.white),
                ),
                onTap: () => {
                      Navigator.of(context).pop(),
                      Navigator.push(context,
                          MaterialPageRoute(builder: (context) => Settings())),
                    }),
            ListTile(
              leading: Icon(
                Icons.logout,
                color: Colors.white,
              ),
              title: Text(
                'Sign Out',
                style: TextStyle(color: Colors.white),
              ),
              onTap: () => showDialog(
                context: context,
                builder: (BuildContext context) {
                  return AlertDialog(
                    title: Text('Confirmation'),
                    titleTextStyle:
                        TextStyle(color: Colors.white, fontSize: 20),
                    content: Text('Are you sure you want to sign out?'),
                    contentTextStyle: TextStyle(color: Colors.white),
                    backgroundColor: Color.fromRGBO(57, 57, 57, 1),
                    actions: <Widget>[
                      TextButton(
                          onPressed: () {
                            Navigator.of(context).pop();
                          },
                          child: Text('Cancel',
                              style: TextStyle(
                                  color: Color.fromRGBO(239, 242, 42, 1)))),
                      TextButton(
                        onPressed: () {
                          Navigator.of(context).pop();
                          Navigator.pushAndRemoveUntil(
                              context,
                              MaterialPageRoute(
                                  builder: (context) => LoginPage()),
                              (route) => false);
                        },
                        child: Text('Sign Out',
                            style: TextStyle(
                                color: Color.fromRGBO(239, 242, 42, 1))),
                      ),
                    ],
                  );
                },
              ),
            )
          ],
        ),
      ),
    );
  }

///////Storing image///////
// void storeData() async{
//   final ap = Provider.of<AuthProvider>(context, listen: false)
//   UserModel userModel = UserModel(ProfilePic: "");
//   if (image != null){
//   // Firebase logic
//   }else {
//     showSnackbar(context, "Please upload your image");
//   }
// }
}
