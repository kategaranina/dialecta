# Automatic annotation
## Normalization model
Before applying automatic annotation make sure that the appropriate normalization model is chosen. 
Go to `Normalization > Models` (from the main menu). You will see the list of currently available models. Each model is linked to the specific `Dialect`:

![alt text][model-dialect]

[model-dialect]: img/trimco-model-dialect-line.png "Dialect"

Make sure that for the recording you want to annotate you have chosen the same `Dialect` at the bottom of the recording's moderation page (`Corpora > Recordings > recording_name`) as the normalization model you want to use has:

![alt text][rec-dialect]

[model-dialect]: img/trimco-rec-dialect-line.png "Recording's dialect"

## Auto-annotation
To perform automatic noramlization and morphological annotation of the whole elan file go to the recording's moderation page (`Corpora > Recordings > recording_name`) and click `Perform automatic annotation`:

![alt text][auto-annotation]

[auto-annotation]: img/trimco-auto-annotation-line.png "Auto-annotation"

This would take a while (about a minute, depending on the recording's length) so please be patient)

When automatic annotation is finally done, the standart transcription view will open. You can make manual changes as usual in the workbench to the right. To open it, simply click on the token you want to annotate, then click the button to right of the line with normalization inside the workbench:
![alt text][manual-annotation-1]

[manual-annotation-1]: img/trimco-manual-annotation-line.png "Manual annotation"

To apply manual annotation click the button to the left of `Select annotation` inside the workbench:
![alt text][manual-annotation-2]

[manual-annotation-2]: img/trimco-manual-annotation-2-line.png "Manual annotation 2"

When you are satisfied with the result, click `save` in the upper right corner to save changes to the elan-file.

Note that **elan-files are not saved automatically after this operation!** (This mean that if you don't like the result of automatic annotation for some reason, you can just go back to the menu and these changes would not be saved)

After auto-annotation is performed, the `Automatically annotated` status of the recording would automatically change to `True` (green tick)

![alt text][status-1]

[status-1]: img/trimco-status-line.png "Auto-annotation status"

![alt text][status-2]

[status-2]: img/trimco-status-info-line.png "Auto-annotation status 2"
