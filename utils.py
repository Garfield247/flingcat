import subprocess


class FlingCatTools:
    @classmethod
    def addWinDefnderWhite(cls, file_path):
        # 添加文件到Windows Defender的白名单
        try:
            command = f"powershell Add-MpPreference -ExclusionPath '{file_path}'"
            subprocess.run(command, shell=True)
        except Exception as err:
            print(err)
