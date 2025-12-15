import os
from pathlib import Path

import bokeh.embed
import numpy as np
import pandas as pd

from bokeh.models import HoverTool, LogColorMapper, DataTable, TableColumn, Arrow, NormalHead, Label, CustomJS, TextInput, Div, CheckboxGroup
from bokeh.models.widgets import Select, Button
from bokeh.plotting import ColumnDataSource
from bokeh.layouts import gridplot, column,row

from pydatalab.blocks.base import DataBlock, event, generate_js_callback_single_float_parameter
from pydatalab.bokeh_plots import DATALAB_BOKEH_THEME, selectable_axes_plot
from pydatalab.file_utils import get_file_info_by_id
from pydatalab.logger import LOGGER

"""A block that loads DSC data, generates a plot
and stores direct DSC data and user-inputted thermodynamic parameters in the database.

TODO:

    1. Replace this class implementation with your own.
    2. Update the entrypoint in pyproject.toml to point to this class.

"""

from pathlib import Path

from pydatalab.blocks.base import DataBlock

from datalab_app_plugin_dsc._version import __version__


class DSCDataBlock(DataBlock):
    version = __version__
    accepted_file_extensions = ('.txt',) # Come back to this
    blocktype = "dsc"
    name = "DSC"
    description = (
            "This block can plot heat flux DSC data from a .txt file exported from TA Instrumnets Universal Analysis 2000 software"
    )

    @property
    def plot_functions(self):
        return (self.generate_dsc_plot,)

    @event()
    def set_data(self,data,name):
    """
    Updates self.data with user-inputted data, or clears the entry in self.data if the input is 'clear'
    Args:
        data: float or comma-separated list containing the information to be added to self.data, or 'clear' to remove the data
        name: string, the name of the variable in self.data to be updated
    """
        datalist = []
        if isinstance(data,float) or isinstance(data,int):
            datalist.append(data)
        elif isinstance(data,str) and data != 'clear':
            try:
                data = data.split(',')
                for i in range(len(data)):
                    datalist.append(float(data[i]))
            except Exception:
                raise ValueError(f"Invalid {name}. Must be a float, comma-separated list of floats, or 'clear' to remove data.")

        LOGGER.debug(f"Setting {name} to {data}")
        self.data[f"{name}_list"] = datalist
        if self.data[f"{name}_list"] == 'clear':
            self.data.pop([f"{name}_list"])


    @event()
    def set_Tg(self, Tg):
        """
        Calls set_data to update the Tg value stored in self.data
        Args:
            Tg: float or comma-separated list containing the Tg data, or 'clear' to remove the data
        """
        self.set_data(Tg, 'Tg')

    @event()
    def set_Tm(self, Tm):
        """
        Calls set_data to update the Tm value stored in self.data
        Args:
            Tm: float or comma-separated list containing the Tm data, or 'clear' to remove the data
        """
        self.set_data(Tm, 'Tm')

    @event()
    def set_cc(self, cc):
        """
        Calls set_data to update the cc value stored in self.data
        Args:
            cc: float or comma-separated list containing the cc data, or 'clear' to remove the data
        """
        self.set_data(cc, 'cold_crystallisation_temp')

    @event()
    def set_ct(self, ct):
        """
        Calls set_data to update the ct value stored in self.data
        Args:
            ct: float or comma-separated list containing the ct data, or 'clear' to remove the data
        """
        self.set_data(ct, 'crystallisation_temp')

    @event()
    def set_cp(self, cp):
        """
        Calls set_data to update the cp value stored in self.data
        Args:
            cp: float or comma-separated list containing the cp data, or 'clear' to remove the data
        """
        self.set_data(cp, 'crystallinity_perc')

    @event()
    def set_Hm(self, Hm):
        """
        Calls set_data to update the Hm value stored in self.data
        Args:
            Hm: float or comma-separated list containing the Hm data, or 'clear' to remove the data
        """
        self.set_data(Hm, 'melting_enthalpy')

    @event()
    def set_Hcc(self, Hcc):
        """
        Calls set_data to update the Hcc value stored in self.data
        Args:
            Hcc: float or comma-separated list containing the Hcc data, or 'clear' to remove the data
        """
        self.set_data(Hcc, 'cold_crystallisation_enthalpy')

    @classmethod
    def parse_dsc_sheet(cls,filename: Path) -> pd.DataFrame:
        """Parses DSC data in a .txt file gnerated from TA Instruments Universal Analysis Software

        The file consists of a header block with metadata information and a data block with signals read by the spectrometer
        This function reads the file, extracts information on how many and which signals are present
        from the metadata, and then parses the signal data into a pandas DataFrame
        Args:
            filename: Path to the .txt file

        Returns:
            dsc: DataFrame containing columns for each signal in the file
            sigs: list of the signals' names
            cycles: DataFrame containing a row for each cylce with a column describing it
            exo: string giving the direction of exothermic change
        """
        # Read the text
        try:
            with open(filename,'r') as f:
                dscraw = f.readlines()
        except:
            with open(filename,'r',encoding='utf-16') as f:
                dscraw = f.readlines()
        for line in dscraw:
            if line.strip().split()[0] == 'Nsig':
                Nsig = int(line.strip().split()[1])
        # Get the number of different signals
        sigs = []
        for i in range(Nsig):
            for line in dscraw:
                if line.strip().split()[0] == 'Sig{0}'.format(i+1):
                    sigs.append(' '.join(line.strip().split()[1:]))
        # Get information on what cycles there are
        cycles = []
        for line in dscraw:
            if line.strip().split()[0] == 'OrgMethod':
                cycles.append(line.strip().split()[1:])
        for i in range(len(cycles)):
            cycles[i] = [cycles[i][0].replace(':',''),' '.join(cycles[i][1:])]
        cycles = pd.DataFrame(cycles)
        cycles.columns=['Step','Description']
        # Get whether exothermic change is up or down
        exo = ''
        for i in range(len(dscraw)):
            if dscraw[i].strip().split()[0] == 'Exotherm':
                exo = dscraw[i].strip().split()[1]
        # Get the data from the cycles
        for i in range(len(dscraw)):
            if dscraw[i].strip() == 'StartOfData':
                dscstart = i
        dscnums = dscraw[dscstart+1:]
        for i in range(len(dscnums)):
            dscnums[i] = dscnums[i].strip().split()
            for j in range(len(dscnums[i])):
                dscnums[i][j] = float(dscnums[i][j])
        dsc = pd.DataFrame(data=dscnums,columns=sigs)
        return dsc,sigs,cycles,exo

#    @classmethod
    def _format_dsc_plot(self, dsc_data: pd.DataFrame,sigs: list, cycleinfo: pd.DataFrame,exo:str) -> bokeh.layouts.layout:
        """Formats DSC data for plotting in bokeh
        Args:
            dsc_data (pd.DataFrame): DSC data with columsn for the signals that were present in the .txt. file
            sigs (list): List of the names of the signals
            cycleinfo (pd.DataFrame): Containing a description of each heat cycling step
            exo (str): The direction of exothermic change, read from the file
        Returns:
            bokeh.layouts.layout: Bokeh layout with DSC data plotted with options for which signals to plot
        """
        # Remove the rows which indicate a change in heat cycle - they will add discontinuity to the plot
        # Currently this is based on finding rows which have a discontinuity from their neighbours
        # as it isn't clear what else indicates these rows
        # In future a better way to detect them could be found
        # And separating the different cycles to allow plotting of only selected cycles could be added
        toremove = []
        for i in range(len(dsc_data)):
            discont = []
            for col in dsc_data.columns.to_list():
                if i == 0:
                    nextdiff = abs(dsc_data[col][i+1] - dsc_data[col][i])
                    if nextdiff > 0.1:
                        discont.append('yes')
                    else:
                        discont.append('no')
                elif i == len(dsc_data)-1:
                    prevdiff = abs(dsc_data[col][i] - dsc_data[col][i-1])
                    if prevdiff > 0.1:
                        discont.append('yes')
                    else:
                        discont.append('no')
                else:
                    prevdiff = abs(dsc_data[col][i] - dsc_data[col][i-1])
                    nextdiff = abs(dsc_data[col][i+1] - dsc_data[col][i])
                    if prevdiff > 0.1 and nextdiff > 0.1:
                        discont.append('yes')
                    else:
                        discont.append('no')
            if all(check == 'yes' for check in discont):
                toremove.append(i)
        dsc_data = dsc_data.drop(toremove)
        # Make the layout of the plot
        plotlayout = selectable_axes_plot(
            dsc_data,
            x_options=sigs,
            y_options=sigs,
            x_default='Temperature (°C)',
            y_default='Heat Flow (mW)',
            plot_points=False,
            plot_line=True,
        )
        # Add indication of direction of exothermic change
        # Position the arrow on the y axis according to the bottom of the heat flow data range
        if exo == 'UP':
            arrowystart = min(dsc_data['Heat Flow (mW)'])
            arrowyend = min(dsc_data['Heat Flow (mW)'])+0.1*(max(dsc_data['Heat Flow (mW)'])-min(dsc_data['Heat Flow (mW)']))
        elif exo == 'DOWN':
            arrowyend = min(dsc_data['Heat Flow (mW)'])
            arrowystart = min(dsc_data['Heat Flow (mW)'])+0.1*(max(dsc_data['Heat Flow (mW)'])-min(dsc_data['Heat Flow (mW)']))
        else:
            LOGGER.warning('Exothermic direction information not found in file')
        # Determine where the arrow would be positioned on the x-axis according to what the x axis is
        arrowxpos = {}
        for sig in sigs:
            arrowxpos[sig] = min(dsc_data[sig])
        # Make the arrow
        arrow = Arrow(x_start=arrowxpos['Temperature (°C)'],\
                    y_start=arrowystart,
                    x_end=arrowxpos['Temperature (°C)'],\
                    y_end=arrowyend,
                    end=NormalHead(size=10),\
                    visible=True
                    )
        # Make a label for the arrow
        arrowlab = Label(x=arrowxpos['Temperature (°C)'],
                        x_offset=10,
                        y=min(dsc_data['Heat Flow (mW)']),
                        text='exo',
                        visible=True)
        # Add the arrow and label to the figure
        plotlayout.children[1].add_layout(arrow)
        plotlayout.children[1].add_layout(arrowlab)

        # Make the arrow visible only if the y axis is heat flow
        plotlayout.children[1].yaxis.js_on_change('axis_label',\
                                                CustomJS(args=dict(arrow=arrow,\
                                                                    arrowlab=arrowlab),\
                                                        code = """
                                                        if (cb_obj.axis_label == 'Heat Flow (mW)') {
                                                            arrow.visible = true
                                                            arrowlab.visible = true
                                                            }
                                                        else {
                                                            arrow.visible = false
                                                            arrowlab.visible = false
                                                            }
                                                        """
                                                        ))
        # Set the arrow's x axis position so that it is near the axis based on the variable plotted
        plotlayout.children[1].xaxis.js_on_change('axis_label',\
                                                CustomJS(args=dict(arrow=arrow,\
                                                                    arrowlab=arrowlab,
                                                                    arrowxpos=arrowxpos),\
                                                        code = """
                                                        arrow.x_start=arrowxpos[cb_obj.axis_label]
                                                        arrow.x_end=arrowxpos[cb_obj.axis_label]
                                                        arrowlab.x=arrowxpos[cb_obj.axis_label]
                                                        """
                                                        ))
                                                           
        # Add a table saying what the cycles were
        longests = []
        for i in range(len(cycleinfo.columns.to_list())):
            lens = [len(cycleinfo.columns.to_list()[i])]
            for j in range(len(cycleinfo)):
                lens.append(len(cycleinfo[cycleinfo.columns.to_list()[i]][j]))
            longests.append(max(lens))
        cycletab = DataTable(
            source=ColumnDataSource(cycleinfo),
            columns=[TableColumn(field=cycleinfo.columns.to_list()[i],width=longests[i]*10)\
                    for i in range(len(cycleinfo.columns.to_list()))],\
            autosize_mode='none',\
            height = 50+25*len(cycleinfo)
            )

        # Add checkbox for whether to show thermodynamic parameters and boxes to input them
        inptoggle = CheckboxGroup(labels=['Show/enter thermodynamic parameters?'],active=[0]) 

        # Add user input options for the thermodynamic information
        inptitle = Div(text='<p style="font-size:16px; "><b>Optional user inputs for values obtained from DSC curve analysis</b></p><br>Entering values will overwrite any already stored<br>If inputting more than one, separate with a comma<br>Enter "clear" to remove stored data for the parameter',visible=True)

        thermparms = ['Tg','Tm','cc','ct','cp','Hm','Hcc']
        thermnames = ['Tg','Tm','cold_crystallisation_temp','crystallisation_temp','crystallinity_perc',\
                'melting_enthalpy','cold_crystallisation_enthalpy']
        thermlabs = ["Glass transition temperature(s) (°C)","Melting temperature(s) (°C)",\
                    "Cold crystallisation temperature(s) (°C)","Crystallisation temperature(s) (°C)",\
                    "% Crystallinity/ies","Melting enthalpy/ies (kJ/mol)",\
                    "Cold crystallisation enthalpy/ies (kJ/mol)"]
    
        # Set up the boxes to enter the thermodynamic parameters with currently stored values under them
        inps = []
        texts = []
        shows = []
        titles = []
        for i in range(len(thermparms)):
            inps.append(TextInput(value = "",title = thermlabs[i],visible=True))
            if '{0}_list'.format(thermnames[i]) in self.data:
                textlist = self.data['{0}_list'.format(thermnames[i])]
                for j in range(len(textlist)):
                    textlist[j] = str(textlist[j])
                texts.append(', '.join(textlist))
                if len(texts[i]) == 0:
                    texts[i] = 'None currently stored (empty list in database)'
            else:
                texts.append('None currently stored')
            shows.append(Div(text = texts[i],style={'font-size':'16px'},visible=True))
            titles.append(Div(text = '<p style="font-size:14px; "><b>Current stored value(s)</b></p>',visible=True))

        # Update values on pressing enter when text is input - link to the display
        for i in range(len(thermparms)):
            inps[i].js_link('value',shows[i],'text')
            shows[i].js_on_change('text',*[CustomJS(code=generate_js_callback_single_float_parameter("set_{0}".format(thermparms[i]),thermparms[i],self.block_id,throttled=False))])

        # Toggle whether the thermodynamic parameter info will be visible based on the checkbox
        inptoggle.js_on_click(CustomJS(args=dict(inptitle=inptitle,inps=inps,shows=shows,titles=titles),\
                code = """
                inptitle.visible = cb_obj.active.includes(0)
                for (let inpcount = 0; inpcount < inps.length; inpcount++) {
                    inps[inpcount].visible = cb_obj.active.includes(0)
                    }
                for (let showcount = 0; showcount < shows.length; showcount++) {
                    shows[showcount].visible = cb_obj.active.includes(0) 
                    }
                for (let titlecount = 0; titlecount < titles.length; titlecount++) {
                    titles[titlecount].visible = cb_obj.active.includes(0)
                    }
                """)
                )
       
        Tgcurrent = column(children = [titles[0],shows[0]])
        Tglayout = row(children = [inps[0],Tgcurrent])
        Tmcurrent = column(children = [titles[1],shows[1]])
        Tmlayout = row(children = [inps[1],Tmcurrent])
        cccurrent = column(children = [titles[2],shows[2]])
        cclayout = row(children = [inps[2],cccurrent])
        ctcurrent = column(children = [titles[3],shows[3]])
        ctlayout = row(children = [inps[3],ctcurrent])
        cpcurrent = column(children = [titles[4],shows[4]])
        cplayout = row(children = [inps[4],cpcurrent])
        Hmcurrent = column(children = [titles[5],shows[5]])
        Hmlayout = row(children = [inps[5],Hmcurrent])
        Hcccurrent = column(children = [titles[6],shows[6]])
        Hcclayout = row(children = [inps[6],Hcccurrent])

        # Put the items together in a bokeh layout
        fulllayout = column(
                children = [
                    plotlayout,
                    cycletab,
                    inptoggle,
                    inptitle,
                    Tglayout,Tmlayout,cclayout,ctlayout,cplayout,Hmlayout,Hcclayout
                    ],
                sizing_mode='stretch_width'
                )
        return fulllayout

    def generate_dsc_plot(self):
        file_info = None
        dsc_data = None

        if "file_id" not in self.data:
            LOGGER.warning("No file set in the DataBlock")
            return
        else:
            file_info = get_file_info_by_id(self.data["file_id"], update_if_live=True)
            ext = os.path.splitext(file_info["location"].split("/")[-1])[-1].lower()
            if ext not in self.accepted_file_extensions:
                LOGGER.warning(
                    "Unsupported file extension (must be one of %s, not %s)",
                    self.accepted_file_extensions,
                    ext,
                )
                return
            
            dsc_data,signals,cycles,exo = self.parse_dsc_sheet(Path(file_info["location"]))
        
        if dsc_data is not None:
            layout = self._format_dsc_plot(dsc_data,signals,cycles,exo)
            self.data["bokeh_plot_data"] = bokeh.embed.json_item(layout, theme=DATALAB_BOKEH_THEME)
