import 'package:flutter/material.dart';
import '/components/appbar.dart';

class Settings extends StatefulWidget {
  const Settings({Key? key}) : super(key: key);

  @override
  _SettingsState createState() => _SettingsState();
}

class _SettingsState extends State<Settings> {
  bool isSwitched1 = false;
  bool isSwitched2 = false;

  TextEditingController feedbackController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const PreferredSize(
        preferredSize: Size.fromHeight(45),
        child: appbar(),
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            radius: 6,
            colors: [
              Color.fromRGBO(57, 57, 57, 1),
              Color.fromRGBO(28, 28, 28, 1),
            ],
          ),
        ),
        child: ListView.builder(
          itemCount: 4,
          itemBuilder: (context, index) {
            return ListTile(
              title: _buildTileContent(index),
            );
          },
        ),
      ),
    );
  }

  Widget _buildTileContent(int index) {
    switch (index) {
      case 0:
        return ListTile(
          title: const Text(
            'General',
            style: TextStyle(fontSize: 20, color: Colors.white),
          ),
          leading: const Icon(
            Icons.info_outline_rounded,
            size: 30,
            color: Colors.white,
          ),
          onTap: () {
            _showVersionInfoDialog(context);
          },
        );
      case 1:
        return ListTile(
            title: const Text(
              'Language',
              style: TextStyle(fontSize: 20, color: Colors.white),
            ),
            subtitle: const Text(
              'English',
              style: TextStyle(
                fontSize: 15,
                color: Colors.white,
              ),
            ),
            leading: const Icon(
              Icons.language_rounded,
              size: 30,
              color: Colors.white,
            ),
            onTap: () {
              switch (index) {
                case 0:
                  const ListTile(
                    title: Text(
                      'English',
                      style: TextStyle(fontSize: 20, color: Colors.white),
                    ),
                  );
                case 1:
                  ListTile(
                    title: const Text(
                      'Hindi',
                      style: TextStyle(fontSize: 20, color: Colors.white),
                    ),
                  );
              }
            });

      case 2:
        return SwitchListTile(
          activeColor: Colors.white,
          title: const Text(
            'Allow Notifications',
            style: TextStyle(fontSize: 20, color: Colors.white),
          ),
          value: isSwitched1,
          onChanged: (value) {
            setState(() {
              isSwitched1 = value;
            });
          },
          secondary: const Icon(Icons.circle_notifications_rounded,
              size: 30, color: Colors.white),
        );
      case 3:
        return ListTile(
          title: const Text(
            'User Account',
            style: TextStyle(fontSize: 20, color: Colors.white),
          ),
          subtitle: const Text(
            'Delete',
            style: TextStyle(fontSize: 15, color: Colors.white),
          ),
          leading: const Icon(Icons.account_circle_rounded,
              size: 30, color: Colors.white),
          trailing: IconButton(
            icon: const Icon(Icons.delete, size: 30, color: Colors.white),
            onPressed: () {
              // Handle delete tap if needed
            },
            color: Colors.black,
          ),
        );
      default:
        return Container();
    }
  }

  void _showVersionInfoDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text('Version Info'),
          content: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Add your version information here.'),
              SizedBox(height: 16),
              Text('Feedback:'),
              TextField(
                controller: feedbackController,
                maxLines: 3,
                decoration: InputDecoration(
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () {
                // Handle feedback submission (you can print or send it)
                String feedback = feedbackController.text;
                print('Feedback submitted: $feedback');
                Navigator.of(context).pop();
              },
              child: Text('Submit'),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
              },
              child: Text('Close'),
            ),
          ],
        );
      },
    );
  }
}
