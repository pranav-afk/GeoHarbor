import 'package:flutter/material.dart';
//import 'package:flutter_application_1/pages/voice_assist.dart';

class Appbar extends StatelessWidget {
  const Appbar({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      iconTheme: IconThemeData(color: Colors.white),
      backgroundColor: Colors.transparent,
      flexibleSpace: SafeArea(
        child: Container(
          decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Color.fromRGBO(57, 57, 57, 1),
                      Color.fromRGBO(28, 28, 28, 1),
                    ],
                  ),
                ),
          child: Stack(
            alignment: Alignment.center,
            children: [
              Container(
                
                child: Image.asset(
                  'lib/images/bhuvan_header.jpg',
                  height: 50,
                ),
              ),
              // Positioned(
              //   right: 0,
              //   child: Container(
              //     width: 50, // Adjust the width as needed
              //     color: Colors.transparent, // Example color, customize as needed
              //     child: Center(
              //       child: IconButton(
              //         icon: Icon(Icons.mic,color: Colors.white,),
              //         onPressed: () {
              //           Navigator.of(context).pop(); 
              //           Navigator.push(
              //             context,
              //             MaterialPageRoute(builder: (context) => Voice()));
              //         },
              //       ),
              //     ),
              //   ),
              // ),
            ],
          ),
        ),
      ),
    );
  }
}
