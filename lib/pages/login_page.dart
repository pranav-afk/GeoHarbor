import 'package:flutter/material.dart';

import '../components/homeappbar.dart';

class LoginPage extends StatelessWidget {
  const LoginPage({super.key});
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Color.fromRGBO(66, 66, 66, 1),
          appBar:const PreferredSize(
            preferredSize:Size.fromHeight(45) ,
            child: Appbar(),
          ),
      body:
      SafeArea(
        child: Column(
          children: [SizedBox(height: 20,),Container(
            child: const Text(
              "Your Profile",
              style: TextStyle(
                color: Color.fromRGBO(239, 242, 42, 1),
                fontWeight: FontWeight.bold,
              ),
            ),
          ),SizedBox(height: 55,),
            Row(
              children: [SizedBox(width: 40,),
                Container(
                    child: const Text(
                      "UserID",
                      style: TextStyle(
                        fontSize: 16,
                            color: Colors.white,
                        ),
                    ),

                ),

              ],
            ),
            SizedBox(height: 5,),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 30),
              child: TextField(
                decoration: InputDecoration(
                  enabledBorder: OutlineInputBorder(
                    borderSide: BorderSide(color: Colors.grey)
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderSide: BorderSide(color: Colors.blue)
                  )
                ),
              ),
            )
          ],
        ),
      ),

    );
  }
}
